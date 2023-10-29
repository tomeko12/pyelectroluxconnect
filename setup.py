import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='pyelectroluxconnect',
    version='0.3.20',
    description='Interface for Electrolux Connectivity Platform API',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/tomeko12/pyelectroluxconnect',
    author='tomeko',
    license='Apache Software License',
    classifiers=[
            'Programming Language :: Python :: 3.10',
            'License :: OSI Approved :: Apache Software License',
            'Operating System :: OS Independent',
            'Topic :: Home Automation',
            'Development Status :: 4 - Beta'
    ],
    keywords='home automation electrolux aeg frigidaire husqvarna',
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    install_requires=[
			'requests>=2.20.0',
			'beautifulsoup4>=4,<5'
	],
    package_data={'': ['certificatechain.pem']},
    zip_safe=False,
)
