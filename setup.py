from setuptools import setup, find_packages

setup(
    name='datauploader',
    version='0.0.3',
    description='yandex load data uplodaer package',
    longer_description='''
yandex load data uplodaer package, used in volta, yandextank projects
''',
    maintainer='Yandex Load public',
    maintainer_email='load-public@yandex-team.ru',
    url='https://github.com/nettorta/DataUploader',
    packages=find_packages(exclude=["tests", "tmp", "docs", "data"]),
    install_requires=[
        'requests',
        'netort',
        'retrying',
    ],
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
    ],
    entry_points={
        'console_scripts': [
        ],
    },
    license='MPLv2',
    package_data={},
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Operating System :: POSIX',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: Software Development :: Testing :: Traffic Generation',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    use_2to3=True, )
