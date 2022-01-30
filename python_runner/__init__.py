from .runner import Runner, PatchedStdinRunner, PatchedSleepRunner

try:
    from .version import __version__
except ImportError:
    # version.py is auto-generated with the git tag when building
    __version__ = "???"
