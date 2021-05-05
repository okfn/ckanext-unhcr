import cgi
from StringIO import StringIO


class FakeFileStorage(cgi.FieldStorage, object):

    def __init__(self, fp=None, filename='test.txt'):
        super(FakeFileStorage, self).__init__()
        self.file = fp
        if not fp:
            self.file = StringIO()
            self.file.write('Some data')

        self.list = [self.file]
        self.filename = filename
        self.name = "upload"
