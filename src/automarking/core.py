# -*- coding: utf-8 -*-
u"""

.. moduleauthor:: Mark Hall <mark.hall@work.room3b.eu>
"""
import re
import tarfile

from csv import DictReader
from os import path
from zipfile import ZipFile

STUDENTNR = re.compile(r'[0-9]{8,9}')


class BlackboardDataSource(object):
    
    def __init__(self, gradebook, gradecolumn):
        self.gradebook_filename = gradebook
        self.gradecolumn_filename = gradecolumn
    
    def __enter__(self):
        studentlist = []
        with open(self.gradecolumn_filename, encoding='utf-8-sig') as in_f:
            reader = DictReader(in_f)
            for line in reader:
                studentlist.append(line['Student ID'])
        submissions = []
        with ZipFile(self.gradebook_filename) as in_f:
            for filename in in_f.namelist():
                match = re.search(STUDENTNR, filename)
                if match and match.group(0) in studentlist:
                    if filename.endswith('.tar.bz2') or filename.endswith('.tar.gz'):
                        target_filename = 'tmp/%s%s' % (match.group(0), filename[filename.find('.'):])
                        with in_f.open(filename) as submission_file:
                            with open(target_filename, 'wb') as out_f:
                                out_f.write(submission_file.read())
                        submissions.append(TarSubmission(match.group(0), target_filename))
                    elif filename.endswith('.txt'):
                        pass
                    else:
                        print('Unknown submission: %s' % filename)
        self.submissions = submissions
        return self.submissions
    
    def __exit__(self, type_, value, traceback):
        for submission in self.submissions:
            print(submission.studentnr)


class Submission(object):
    
    def __init__(self, studentnr):
        self.studentnr = studentnr
        self.score = 0

    def get(self, selection):
        return self.source.get(selection)


class TarSubmission(Submission):
    
    def __init__(self, studentnr, source_filename):
        Submission.__init__(self, studentnr)
        self.file = tarfile.open(source_filename)

    def get(self, selection):
        files = []
        for identifier, pattern in selection:
            for filename in self.file.getnames():
                if re.match(pattern, path.basename(filename)):
                    files.append(SubmissionFile(identifier, pattern, self.file.extractfile(filename)))
        return files


class SubmissionFile(object):
    
    def __init__(self, identifier, pattern, source):
        self.identifier = identifier
        self.pattern = pattern
        self.source = source
        self.score = 0
        self.feedback = []
        
    def __enter__(self):
        return self.source
    
    def __exit__(self, type_, value, traceback):
        pass
