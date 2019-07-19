from setuptools import find_packages, setup

if __name__ == "__main__":
    setup(
        name="hledger-import-app",
        description="Hledger Import App",
        version="0.1",
        url="https://github.com/dat2/hledger-import-app",
        author="Nicholas Dujay",
        author_email="nickdujay@gmail.com",
        maintainer="Nicholas Dujay  ",
        maintainer_email="nickdujay@gmail.com",
        packages=find_packages(where="src"),
        package_dir={"": "src"},
        entry_points={
            "console_scripts": [
                "hledger-import=hledger.import:main",
                "plaid-import=plaid_import.plaid_import:cli",
            ]
        },
        install_requires=["click", "plaid-python", "python-dotenv", "toml", "tqdm"],
        extras_require={"dev": ["black", "invoke", "isort"]},
        zip_safe=False,
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Developers",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: Implementation :: CPython",
        ],
        python_requires="~=3.6",
    )
