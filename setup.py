from setuptools import setup, find_packages

setup(
    name="useful-nmigen",
    description="collection of useful nmigen scripts",
    python_requires="~=3.6",
    setup_requires=["wheel", "setuptools", "setuptools_scm"],
    packages=find_packages(exclude=["tests*"]),
)
