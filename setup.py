from setuptools import setup

setup(name='jitter_usb_py',
      version='0.1',
      description='Interfaces Jitter USB Devices using pyusb',
      url='http://github.com/jittercompany/jitter_usb_py',
      author='Jitter',
      author_email='info@jitter.company',
      license='MIT',
      packages=['jitter_usb_py'],
      install_requires=[
          'PyQt5',
          'pyusb>=1.1'
      ],
      dependency_links=[
          'git+https://github.com/JitterCompany/pyusb.git#egg=pyusb-1.1'
      ],
      zip_safe=False)
