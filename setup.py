from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(name='sgx_crawler',
      packages=find_packages(),
      version='1.0.0',
      author="Junxiao Zhao",
      description="A crawler to download SGX data",
      long_description=long_description,
      long_description_content_type="text/markdown",
      url="https://github.com/Junxiao-Zhao/SGX-web_crawler",
      license="MIT",
      install_requires=['schedule', 'logging_tree', 'requests'],
      py_modules=['sample_crawler'],
      python_requires='>=3.8')
