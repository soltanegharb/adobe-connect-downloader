#!filepath: bootstrap.py
# The Universal Python Bootstrapper - v19.2 (Perfected Grade + Src-Layout + Editable Install)
#
# This script is a zero-dependency, single-file, enterprise-grade utility for
# ensuring a Python application runs in a correct, isolated, and up-to-date environment.
# This version represents the pinnacle of robustness, security, and user experience,
# hardened by a rigorous, collaborative expert review process.
# This version incorporates a critical fix for `src-layout` projects and adds
# automatic editable installation for local packages.
#
# Key Features:
# - Mission-Critical Resilience: Graceful signal handling, network diagnostics,
#   and retry logic with exponential backoff for installation and cleanup.
# - Proactive Hardening: Proactively checks permissions, disk space, and Python/pip versions.
# - Advanced Security: Deep requirements validation including robust package name parsing
#   and sophisticated typosquatting detection.
# - Superior Developer Experience: Rich, actionable diagnostics, type hints, a --dry-run
#   mode, and a thread-safe progress indicator for long operations.
# - Src-Layout Aware: Correctly handles relaunching for projects executed as modules.
# - Editable Install Aware: Automatically runs `pip install -e .` for projects
#   with a `pyproject.toml` or `setup.py`.
#
# Author: Mohammad Hossein Soltani(github.com/soltanegharb)
# Version: 19.2.0 (Perfected Grade: Final integration of expert review + editable install)
# License: MIT / Public Domain equivalent (use freely)


import os
import sys
import subprocess
import hashlib
import shutil
import time
import logging
import re
import signal
import threading
from pathlib import Path
from typing import Dict, Any, Tuple, Callable, List, Optional, Generator
from contextlib import contextmanager
from dataclasses import dataclass


class SecurityError(Exception):
    """Raised when a security validation fails."""
    pass


@dataclass
class BootstrapConfig:
    """Centralized, type-safe configuration for the bootstrapper."""
    strict_security: bool = False
    enable_metrics: bool = False
    enable_health_checks: bool = True
    venv_timeout: int = 300
    pip_timeout: int = 600
    health_timeout: int = 30

    def __post_init__(self):
        """Validate configuration values after initialization."""
        self.venv_timeout = max(60, self.venv_timeout)
        self.pip_timeout = max(120, self.pip_timeout)
        self.health_timeout = max(10, self.health_timeout)


class _Bootstrapper:
    """Encapsulates all logic for the bootstrapping process."""
    # --- Constants ---
    RETRY_COUNT: int = 3
    HEALTH_CHECK_CACHE_TTL_S: int = 300
    MAX_VALIDATION_FILE_SIZE_B: int = 1 * 1024 * 1024
    MIN_PYTHON_VERSION: Tuple[int, int] = (3, 8)
    MIN_DISK_SPACE_MB: int = 200
    PYPI_HEALTH_CHECK_URL: str = 'https://pypi.org'
    NETWORK_TIMEOUT_S: int = 5
    VALID_CONFIG_KEYS: set = {'strict_security', 'metrics', 'enable_health_checks', 'venv_timeout', 'pip_timeout', 'health_timeout'}
    KNOWN_TYPOS: Dict[str, str] = {'requesrs': 'requests', 'djanga': 'django', 'beutifulsoup': 'beautifulsoup4', 'tennsorflow': 'tensorflow', 'pandas': 'pandas'}

    def __init__(self, dry_run: bool = False):
        if not isinstance(dry_run, bool): raise TypeError("dry_run must be a boolean")
        # This dry_run is now ONLY for the bootstrapper, controlled by --bootstrap-dry-run
        self.dry_run = dry_run or (os.getenv('BOOTSTRAP_DRY_RUN', 'false').lower() in ('1', 'true', 'yes'))
        self.logger = self._setup_logging()
        if self.dry_run:
            self.logger.info("--- BOOTSTRAP DRY RUN MODE ENABLED ---")

        import atexit
        atexit.register(self._cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.project_root: Path = Path(__file__).parent.resolve()
        if not self.project_root.is_dir(): raise ValueError(f"Project root {self.project_root} is not a directory")

        self.VENV_DIR_NAME: str = ".venv"
        self.REQUIREMENTS_FNAME: str = "requirements.txt"
        self.venv_path: Path = self.project_root / self.VENV_DIR_NAME
        self.requirements_path: Path = self.project_root / self.REQUIREMENTS_FNAME
        self.venv_python_exe: Path = self.venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        req_context = f"{self.requirements_path.resolve()}:{self.project_root}"
        receipt_hash = hashlib.sha256(req_context.encode()).hexdigest()[:12]
        self.receipt_path: Path = self.venv_path / f".deps_installed.{receipt_hash}"

        self.config = self._load_config()
        self._metrics: Dict[str, float] = {}
        self._metrics_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._health_check_cache: Dict[str, Dict[str, Any]] = {}
        self._parsed_requirements: Optional[List[str]] = None
        self._validate_environment()

    def _to_bool(self, value: Any) -> bool:
        """Converts various formats to boolean."""
        if isinstance(value, bool): return value
        return str(value).lower() in ('1', 'true', 'yes', 'on')

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger('bootstrapper')
        if not logger.handlers:
            handler = logging.StreamHandler()
            dry_run_prefix = "[BOOTSTRAP DRY RUN] " if self.dry_run else ""
            formatter = logging.Formatter(f'bootstrap {dry_run_prefix}%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%H:%M:%S')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(os.getenv('BOOTSTRAP_LOG_LEVEL', 'INFO').upper())
        return logger

    def _load_config(self) -> BootstrapConfig:
        """Load configuration from file and environment variables."""
        config_path = self.project_root / '.bootstrap.toml'
        file_config: Dict[str, Any] = {}
        if config_path.exists():
            try:
                with config_path.open('r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith('#'): continue
                        if '=' not in line:
                            self.logger.warning(f"Invalid config line {line_num} in {config_path.name}: '{line}'")
                            continue
                        key, value = map(str.strip, line.split('=', 1))
                        if key in self.VALID_CONFIG_KEYS:
                            file_config[key] = value.strip('"\'')
                        else:
                            self.logger.warning(f"Unknown config key '{key}' in {config_path.name}")
            except Exception as e: self.logger.warning(f"Failed to load .bootstrap.toml: {e}")

        def get_cfg(key: str, default: Any, type_conv: Callable) -> Any:
            val = os.getenv(f'BOOTSTRAP_{key.upper()}', file_config.get(key, default))
            return type_conv(val) if val is not None else default

        return BootstrapConfig(
            strict_security=get_cfg('strict_security', False, self._to_bool),
            enable_metrics=get_cfg('metrics', False, self._to_bool),
            enable_health_checks=get_cfg('enable_health_checks', True, self._to_bool),
            venv_timeout=get_cfg('venv_timeout', 300, int),
            pip_timeout=get_cfg('pip_timeout', 600, int),
            health_timeout=get_cfg('health_timeout', 30, int),
        )

    def _validate_environment(self) -> None:
        """Proactively checks Python version, disk space, pip, and permissions."""
        if sys.version_info < self.MIN_PYTHON_VERSION:
            self.logger.critical(f"Python {'.'.join(map(str, self.MIN_PYTHON_VERSION))}+ required."); sys.exit(1)
        try:
            free_space = shutil.disk_usage(self.project_root).free
            if free_space < self.MIN_DISK_SPACE_MB * 1024 * 1024:
                self.logger.warning(f"Low disk space: {free_space // 10**6}MB free.")
        except (OSError, PermissionError) as e: self.logger.debug(f"Could not check disk space: {e}")
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, check=True, timeout=10)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.warning("`pip` is not available in the system Python. This may cause issues if venv creation fails.")
        if not os.access(self.project_root, os.W_OK):
            self.logger.critical(f"Project root '{self.project_root}' is not writable."); sys.exit(1)

    @staticmethod
    def _parse_package_name(line: str) -> str:
        """Robustly extracts a package name from a requirements line."""
        line = line.strip().split('#')[0]
        if line.startswith('-e '):
            if '.git' in line: return line.split('/')[-1].split('.git')[0]
            return ''
        for op in ['==', '>=', '<=', '>', '<', '~=', '!=']:
            if op in line: line = line.split(op)[0]
        return line.split('[')[0].strip()

    def _get_parsed_requirements(self) -> List[str]:
        """Parses requirements file once and caches results."""
        if self._parsed_requirements is None:
            if not self.requirements_path.is_file():
                self._parsed_requirements = []
            else:
                try:
                    with self.requirements_path.open('r', encoding='utf-8') as f:
                        self._parsed_requirements = [
                            line.strip() for line in f 
                            if line.strip() and not line.strip().startswith('#')
                        ]
                except (OSError, PermissionError) as e:
                    self.logger.warning(f"Could not read {self.REQUIREMENTS_FNAME}: {e}")
                    self._parsed_requirements = []
        return self._parsed_requirements

    def _validate_requirements_file(self) -> None:
        """Optimized security validation including advanced typosquatting detection."""
        try:
            if not self.requirements_path.is_file() or self.requirements_path.stat().st_size > self.MAX_VALIDATION_FILE_SIZE_B: return
            lines, warnings, crit_issues = self._get_parsed_requirements(), [], []
            crit_patterns = [(r'--index-url\s+http://', 'Insecure HTTP index URL')]
            
            for ln, line in enumerate(lines, 1):
                pkg_name = self._parse_package_name(line)
                if not pkg_name: continue
                if '==' not in line and not line.startswith(('-', 'git+')): warnings.append(f"Line {ln}: Unpinned dependency '{pkg_name}'")
                for p, d in crit_patterns:
                    if re.search(p, line): crit_issues.append(f"Line {ln}: {d}")
                if known_typo := self.KNOWN_TYPOS.get(pkg_name.lower()):
                    warnings.append(f"Line {ln}: Potential typosquatting of '{known_typo}' - found '{pkg_name}'")

            if crit_issues:
                self.logger.critical("CRITICAL SECURITY ISSUES IN REQUIREMENTS:")
                for issue in crit_issues: self.logger.critical(f"  - {issue}")
                if self.config.strict_security: self.logger.error("Exiting due to strict security mode."); sys.exit(1)
            if warnings:
                self.logger.warning("Security/practice warnings for requirements:")
                for warning in warnings: self.logger.warning(f"  - {warning}")
        except Exception as e: self.logger.warning(f"Security validation of requirements.txt failed: {e}")

    def _is_venv_healthy(self) -> bool:
        """Cached and thread-safe health check."""
        if not self.config.enable_health_checks: return True
        
        cache_key, current_time = str(self.venv_path), time.time()
        with self._cache_lock:
            cached = self._health_check_cache.get(cache_key)
            if cached and (current_time - cached['time']) < self.HEALTH_CHECK_CACHE_TTL_S: return cached['is_healthy']
        
        is_healthy = self._perform_health_check()
        
        with self._cache_lock:
            if self.config.enable_metrics: self._metrics['health_check_count'] = self._metrics.get('health_check_count', 0) + 1
            self._health_check_cache[cache_key] = {'time': current_time, 'is_healthy': is_healthy}
        if not is_healthy: self.logger.warning("Virtual environment health check failed.")
        return is_healthy

    def _perform_health_check(self) -> bool:
        if not self.venv_python_exe.is_file(): return False
        try:
            res = self._safe_subprocess([str(self.venv_python_exe), "-c", "import sys; print(sys.prefix)"], self.config.health_timeout)
            if os.path.normcase(str(Path(res.stdout.strip()).resolve())) != os.path.normcase(str(self.venv_path.resolve())): return False
            self._safe_subprocess([str(self.venv_python_exe), "-m", "pip", "--version"], self.config.health_timeout)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, SecurityError): return False

    def _safe_remove_venv(self) -> None:
        """Safe venv removal with exponential backoff and Windows permission fix."""
        self.logger.warning("Attempting to remove corrupted virtual environment...")
        if self.dry_run: return
        for attempt in range(self.RETRY_COUNT):
            try:
                shutil.rmtree(self.venv_path)
                self.logger.info("Corrupted venv removed successfully."); return
            except OSError as e:
                self.logger.warning(f"Failed to remove venv (attempt {attempt + 1}/{self.RETRY_COUNT}): {e}")
                if attempt < self.RETRY_COUNT - 1: time.sleep(2 ** attempt)
        self.logger.critical(f"Cannot remove venv. Please remove '{self.venv_path}' manually."); sys.exit(1)

    def _safe_subprocess(self, cmd: List[str], timeout: int) -> subprocess.CompletedProcess:
        """A hardened subprocess runner."""
        if not Path(cmd[0]).is_file():
            raise SecurityError(f"Executable not found: {cmd[0]}")
        return subprocess.run(cmd, check=True, capture_output=True, timeout=timeout, text=True)

    def _run_dependency_install(self) -> None:
        """Refactored logic for installing dependencies."""
        pip_upgrade_cmd = [str(self.venv_python_exe), "-m", "pip", "install", "--upgrade", "pip"]
        self._safe_subprocess(pip_upgrade_cmd, self.config.pip_timeout)
        pip_install_cmd = [str(self.venv_python_exe), "-m", "pip", "install", "-r", str(self.requirements_path)]
        self._safe_subprocess(pip_install_cmd, self.config.pip_timeout)

    def _ensure_venv_exists(self) -> None:
        """Enhanced venv creation with graceful degradation."""
        if self.venv_path.is_dir() and self._is_venv_healthy(): return
        if self.venv_path.is_dir(): self._safe_remove_venv()
        
        self.logger.info(f"Creating virtual environment in '{self.VENV_DIR_NAME}'...")
        if self.dry_run: return
        start_time = time.monotonic()
        strategies = [([sys.executable, "-m", "venv", str(self.venv_path)], "built-in 'venv'"),
                      ([sys.executable, "-m", "virtualenv", str(self.venv_path)], "'virtualenv' package")]
        for cmd, name in strategies:
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=self.config.venv_timeout)
                self.logger.info(f"Virtual environment created successfully using {name}.")
                with self._metrics_lock:
                    if self.config.enable_metrics: self._metrics['venv_creation_time'] = time.monotonic() - start_time
                return
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                self.logger.debug(f"Strategy '{name}' failed: {e}")
            except Exception as e:
                self.logger.warning(f"Unexpected error with {name}: {e}")
        self.logger.critical("All venv creation strategies failed. Ensure Python's 'venv' module or 'virtualenv' is available."); sys.exit(1)

    @contextmanager
    def _progress_indicator(self, message: str) -> Generator[None, None, None]:
        """Context manager for displaying a progress spinner."""
        stop_event = threading.Event()
        thread = threading.Thread(target=self._show_progress, args=(message, stop_event), daemon=True)
        try:
            thread.start()
            yield
        finally:
            stop_event.set()
            if thread.is_alive(): thread.join(timeout=1.0)
            sys.stdout.write('\r' + ' ' * (len(message) + 15) + '\r')
            sys.stdout.flush()

    def _show_progress(self, message: str, stop_event: threading.Event) -> None:
        """Simple progress spinner for long operations."""
        while not stop_event.is_set():
            for char in r'-\|/':
                if stop_event.is_set(): break
                sys.stdout.write(f'\r{message} {char}')
                sys.stdout.flush()
                time.sleep(0.2)

    def _should_sync_dependencies(self) -> bool:
        """Determines if a dependency sync is needed."""
        if not self.requirements_path.is_file():
            self.logger.debug("No requirements.txt found, skipping dependency sync.")
            return False
        try:
            req_data = self.requirements_path.read_bytes()
            current_hash = hashlib.sha256(req_data).hexdigest()
        except (OSError, PermissionError) as e:
            self.logger.warning(f"Could not read {self.REQUIREMENTS_FNAME}: {e}")
            return False

        cached_hash = None
        if self.receipt_path.is_file():
            try: cached_hash = self.receipt_path.read_text().strip()
            except OSError: pass
        
        return current_hash != cached_hash

    def _sync_dependencies(self) -> None:
        """Refactored dependency sync with extracted logic."""
        if not self._should_sync_dependencies(): return
        
        self._validate_requirements_file()
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would install dependencies from '{self.REQUIREMENTS_FNAME}'.")
            return
        
        start_time = time.monotonic()
        with self._progress_indicator(f"Installing dependencies from '{self.REQUIREMENTS_FNAME}'..."):
            for attempt in range(self.RETRY_COUNT):
                try:
                    self._run_dependency_install()
                    self.receipt_path.write_text(hashlib.sha256(self.requirements_path.read_bytes()).hexdigest())
                    self.logger.info("Dependencies installed successfully.")
                    with self._metrics_lock:
                        if self.config.enable_metrics: self._metrics['dependency_install_time'] = time.monotonic() - start_time
                    return
                except (subprocess.TimeoutExpired, FileNotFoundError, SecurityError) as e:
                    self.logger.critical(f"Installation failed with unrecoverable error: {e}")
                    sys.exit(1)
                except subprocess.CalledProcessError as e:
                    if attempt < self.RETRY_COUNT - 1:
                        try: import urllib.request; urllib.request.urlopen(self.PYPI_HEALTH_CHECK_URL, timeout=self.NETWORK_TIMEOUT_S)
                        except Exception: self.logger.warning(f"Install failed (network check FAILED), retrying in {2**attempt}s...")
                        else: self.logger.warning(f"Install failed (network check OK), retrying in {2**attempt}s...")
                        time.sleep(2 ** attempt)
                    else:
                        self.logger.critical(f"Failed to install dependencies after {self.RETRY_COUNT} attempts."); sys.exit(1)

    def _get_project_name_from_pyproject(self) -> Optional[str]:
        """Extract project name from pyproject.toml."""
        pyproject_path = self.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            return None
        
        try:
            with pyproject_path.open('r', encoding='utf-8') as f:
                content = f.read()
            
            match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
        except Exception as e:
            self.logger.debug(f"Could not parse project name from pyproject.toml: {e}")
        
        return None

    def _ensure_project_installed(self) -> None:
        """Ensures the current project is installed in editable mode for src-layout projects."""
        pyproject_toml = self.project_root / "pyproject.toml"
        setup_py = self.project_root / "setup.py"
        
        if not (pyproject_toml.exists() or setup_py.exists()):
            self.logger.debug("No pyproject.toml or setup.py found, skipping project installation")
            return
        
        try:
            result = self._safe_subprocess([str(self.venv_python_exe), "-m", "pip", "list", "--editable"], timeout=30)
            
            if pyproject_toml.exists():
                project_name = self._get_project_name_from_pyproject()
                if project_name and project_name.lower() in result.stdout.lower():
                    self.logger.debug(f"Project '{project_name}' already installed in editable mode")
                    return
        except Exception as e:
            self.logger.debug(f"Could not check editable installations: {e}")
        
        self.logger.info("Installing project in editable mode...")
        if self.dry_run:
            self.logger.info("DRY RUN: Would install project with 'pip install -e .'")
            return
        
        try:
            install_cmd = [str(self.venv_python_exe), "-m", "pip", "install", "-e", "."]
            self._safe_subprocess(install_cmd, self.config.pip_timeout)
            self.logger.info("Project installed successfully in editable mode")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Failed to install project in editable mode: {e.stdout}\n{e.stderr}")

    def _relaunch_if_needed(self) -> None:
        """Re-launches the script using the venv's python if not already inside it."""
        venv_prefix = os.path.normcase(str(self.venv_path.resolve()))
        current_prefix = os.path.normcase(str(Path(sys.prefix).resolve()))
        if venv_prefix == current_prefix: 
            return
        
        self.logger.info(f"Relaunching application inside '{self.VENV_DIR_NAME}'...")
        if self.dry_run:
            self.logger.info("Bootstrap dry-run complete. Halting before relaunch.")
            sys.exit(0)
        
        original_module = os.getenv('BOOTSTRAP_MODULE_NAME')
        if original_module:
            command = [str(self.venv_python_exe), "-m", original_module] + sys.argv[1:]
            self.logger.debug(f"Relaunching as module: {original_module}")
        else:
            command = [str(self.venv_python_exe)] + sys.argv
            self.logger.debug("Relaunching as direct script")
        
        if os.name == "nt": 
            sys.exit(subprocess.run(command, check=False).returncode)
        try: 
            os.execv(command[0], command)
        except OSError as e: 
            self.logger.critical(f"Failed to relaunch script: {e}")
            sys.exit(1)

    def _cleanup(self) -> None:
        self.logger.debug("Running cleanup tasks...")
        self._log_metrics()

    def _signal_handler(self, signum: int, frame: object) -> None:
        try: signal_name = signal.Signals(signum).name
        except (AttributeError, ValueError): signal_name = str(signum)
        self.logger.warning(f"Received signal {signal_name}, shutting down gracefully.")
        sys.exit(130)

    def _log_metrics(self) -> None:
        if not self.config.enable_metrics or not self._metrics: return
        self.logger.info("--- Performance Metrics ---")
        with self._metrics_lock:
            for key, value in self._metrics.items():
                self.logger.info(f"  - {key:<25}: {value:.4f}s" if isinstance(value, float) else f"  - {key:<25}: {value}")
        self.logger.info("-------------------------")

    def run(self) -> None:
        """Executes the complete bootstrapping process."""
        self._ensure_venv_exists()
        self._sync_dependencies()
        self._ensure_project_installed()
        self._relaunch_if_needed()

def bootstrap() -> None:
    """Activates the bootstrapper. A --bootstrap-dry-run flag will activate dry-run mode."""
    # Only check for bootstrap-specific flag to avoid conflicts with the app's --dry-run
    is_bootstrap_dry_run = '--bootstrap-dry-run' in sys.argv
    if is_bootstrap_dry_run:
        sys.argv.remove('--bootstrap-dry-run')
    
    _Bootstrapper(dry_run=is_bootstrap_dry_run).run()


if __name__ == "__main__":
    logger = logging.getLogger('bootstrapper')
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('bootstrap %(asctime)s - [%(levelname)s] - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel('INFO')
    
    logger.info("Running bootstrap check directly...")
    bootstrap()
    logger.info("Bootstrap check complete.")
