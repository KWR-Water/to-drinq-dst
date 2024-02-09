import os
from setuptools import setup, find_packages

def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()

todrinq_dst = 'todrinq_dst'
setup(
    name=todrinq_dst,
    version='0.1',
    packages=find_packages(exclude=['tests*']),
    license='All rights reserved',
    description='A python package to ',
    long_description=read('README.rst'),
    long_description_content_type="text/x-rst",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.9',
        'Topic :: Scientific/Engineering :: Water treatment',
    ],
    python_requires='>=3.9',
    project_urls={
    'Source': f'https://github.com/KWR-Water/{todrinq_dst}',
    'Documentation': f'http://{todrinq_dst}.readthedocs.io/en/latest/',
    'Tracker': f'https://github.com/KWR-Water/{todrinq_dst}/issues',
    'Help': f'https://github.com/KWR-Water/{todrinq_dst}/issues',
    },
    install_requires=[
        'pandas',
        'openpyxl',
        'pytest',
        ],
    url=f'https://github.com/KWR-Water/{todrinq_dst}',
    author='KWR Water Research Institute',
    author_email='martin.korevaar@kwrwater.nl, bas.wols@kwrwater.nl'
)
