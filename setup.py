from setuptools import find_packages, setup

package_name = 'teleop_px4'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lakshya',
    maintainer_email='lakshyabhatnagar01@gmail.com',
    description='Teleoperation interface for PX4 using ROS 2',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'teleop_to_px4 = teleop_px4.teleop_to_px4:main',
        ],
    },
)

