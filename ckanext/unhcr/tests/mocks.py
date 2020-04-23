import cgi
from StringIO import StringIO


class FakeFileStorage(cgi.FieldStorage):

    def __init__(self, fp=None, filename='test.txt'):
        self.file = fp
        if not fp:
            self.file = StringIO()
            self.file.write('Some data')

        self.filename = filename
        self.name = "upload"
