import nox
import os
import glob

@nox.session(python=['3.8', '3.9', '3.10', '3.11', '3.12', '3.13', 'pypy3'])
def tests(session):
    session.run("pdm", "build")

    session.install("pytest")

    # Find the whl packages. We're going to sort by newest to oldest
    # so for testing we can install the freshest copy
    package_files = sorted(
                        glob.glob("dist/swampyer-*.whl"),
                        key=os.path.getmtime,
                        reverse=True
                    )

    if not package_files:
        raise FileNotFoundError("No swampyer-VERSION.whl package found in the 'dist' directory.")

    # Install the built package
    session.install("--force-reinstall", package_files[0]+"[all]")

    # Run tests
    session.run("pytest", "--log-cli-level=WARN", "-s")
