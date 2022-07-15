import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='pytinybeans',
    version='1.0.1',
    author='Adam Hitchcock',
    author_email='adam@northisup.com',
    description='Asyncio Python library to interact with the Tinybeans API',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/northisup/pytinybeans',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
    ],
    python_requires='>=3.9',
    install_requires=['requests', 'inflection', 'pydantic', 'aiohttp'],
    tests_require=[
        'pytest',
    ],
)
