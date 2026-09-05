
# To prevent the Qt GUI integration error in Flask application
# AttributeError: module 'PySide6.QtGui' has no attribute 'QApplication' Backend qtagg is interactive backend. Turning interactive mode on.
import os
import sys
# Set environment variable to disable Qt support before any other imports
os.environ['QT_API'] = 'None'
os.environ['MPLBACKEND'] = 'Agg'  # Use non-GUI matplotlib backend

# Disable matplotlib's automatic GUI selection
try:
    import matplotlib
    matplotlib.use('Agg')  # Force non-interactive backend
except ImportError:
    pass

from pathlib import Path
def main(args=None):
    import argparse
    # from funlab.utils import vars2env
    from funlab.flaskr.app import create_app, start_server
    if not args:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Programing by 013 ...")

    parser.add_argument("-c", "--configfile", dest="configfile", default=str(Path(__file__).parent.joinpath('config.toml')), help="specify config.toml name and path")
    parser.add_argument("-e", "--envfile", dest="envfile", default=str(Path(__file__).parent.joinpath('.env')), help="specify .env file name and path")
    args = parser.parse_args(args)
    configfile=args.configfile
    envfile=args.envfile
    start_server(create_app(configfile=configfile, envfile=envfile))

if __name__ == "__main__":
    import sys

    sys.exit(main())
