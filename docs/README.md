## Build Dependencies

You can build the docs using [Sphinx][sphinx-home] for Python 3 with the 
[napoleon][napoleon-home] extension.

Both can be installed using `pip3` which *should* come packaged with Python &ge;3.4.

```ShellSession
    pip3 install sphinx sphinxcontrib-napoleon
```

Alternatively you can usually find Sphinx packaged as `python3-sphinx` on Linux 
and as `py3{3,4,5}-sphinx` on MacPorts. 

## Building

You can build the docs using

```ShellSession
    make html
```

or check `make help` to see a list of output formats.







[sphinx-home]: http://www.sphinx-doc.org/
[napoleon-home]: https://pypi.python.org/pypi/sphinxcontrib-napoleon
