from setuptools import setup, find_packages

setup(
    name="vci-common",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "camorph @ git+https://github.com/Fraunhofer-IIS/camorph",
    ]
)