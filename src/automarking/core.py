# -*- coding: utf-8 -*-
u"""

.. moduleauthor:: Mark Hall <mark.hall@work.room3b.eu>
"""
import re
import tarfile

from csv import DictReader, DictWriter
from os import path
from rarfile import RarFile
from zipfile import ZipFile

STUDENTNR = re.compile(r'[0-9]{8,9}')


class BlackboardDataSource(object):
    
    def __init__(self, gradebook, gradecolumn, patterns):
        self.gradebook_filename = gradebook
        self.gradecolumn_filename = gradecolumn
        self.patterns = patterns
    
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
                    target_filename = 'tmp/%s%s' % (match.group(0), filename[filename.find('.'):])
                    if filename.lower().endswith('.tar.bz2') or filename.endswith('.tar.gz'):
                        with in_f.open(filename) as submission_file:
                            with open(target_filename, 'wb') as out_f:
                                out_f.write(submission_file.read())
                        submissions.append(TarSubmission(match.group(0), self.patterns, target_filename))
                    elif filename.lower().endswith('.zip'):
                        with in_f.open(filename) as submission_file:
                            with open(target_filename, 'wb') as out_f:
                                out_f.write(submission_file.read())
                        submissions.append(ZipSubmission(match.group(0), self.patterns, target_filename))
                    elif filename.lower().endswith('.rar'):
                        with in_f.open(filename) as submission_file:
                            with open(target_filename, 'wb') as out_f:
                                out_f.write(submission_file.read())
                        submissions.append(RarSubmission(match.group(0), self.patterns, target_filename))
                    elif filename.endswith('.txt'):
                        pass
                    else:
                        print('Unknown submission: %s' % filename)
        self.submissions = submissions
        return self.submissions
    
    def __exit__(self, type_, value, traceback):
        submissions = {}
        for submission in self.submissions:
            submissions[submission.studentnr] = submission
        lines = []
        score_field = None
        with open(self.gradecolumn_filename, encoding='utf-8-sig') as in_f:
            reader = DictReader(in_f)
            fieldnames = [fn if fn != 'Feedback to Learner' else 'Feedback to User' for fn in reader.fieldnames]
            for fieldname in fieldnames:
                if 'Total Pts:' in fieldname:
                    score_field = fieldname
            for line in reader:
                lines.append(line)
        with open(self.gradecolumn_filename, 'w', encoding='utf-8-sig') as out_f:
            writer = DictWriter(out_f, fieldnames=fieldnames)
            writer.writeheader()
            for line in lines:
                if 'Feedback to Learner' in line:
                    del line['Feedback to Learner']
                if line['Student ID'] in submissions:
                    line[score_field] = submissions[line['Student ID']].score
                    line['Feedback to User'] = '\n'.join(submissions[line['Student ID']].feedback)
                else:
                    line[score_field] = 0
                writer.writerow(line)


class Submission(object):
    
    def __init__(self, studentnr):
        self.studentnr = studentnr
        self.score = 0
        self.files = []
        self.feedback = []

    def __enter__(self):
        return self.files

    def __exit__(self, type_, value, traceback):
        self.score = 0
        for submission_file in self.files:
            self.score = self.score + submission_file.score
            self.feedback.extend(submission_file.feedback)


class TarSubmission(Submission):
    
    def __init__(self, studentnr, patterns, source_filename):
        Submission.__init__(self, studentnr)
        source_file = tarfile.open(source_filename)
        self.files = []
        for identifier, pattern, title in patterns:
            for filename in source_file.getnames():
                if re.match(pattern, path.basename(filename)):
                    self.files.append(SubmissionFile(identifier, pattern, title, source_file.extractfile(filename)))


class ZipSubmission(Submission):

    def __init__(self, studentnr, patterns, source_filename):
        Submission.__init__(self, studentnr)
        source_file = ZipFile(source_filename)
        self.files = []
        for identifier, pattern, title in patterns:
            for filename in source_file.namelist():
                if re.match(pattern, path.basename(filename)):
                    self.files.append(SubmissionFile(identifier, pattern, title, source_file.open(filename)))


class RarSubmission(Submission):

    def __init__(self, studentnr, patterns, source_filename):
        Submission.__init__(self, studentnr)
        source_file = RarFile(source_filename)
        self.files = []
        for identifier, pattern, title in patterns:
            for filename in source_file.namelist():
                filename = filename.replace('\\', '/')
                if re.match(pattern, path.basename(filename)):
                    self.files.append(SubmissionFile(identifier, pattern, title, source_file.open(filename)))


class SubmissionFile(object):
    
    def __init__(self, identifier, pattern, title, source):
        self.identifier = identifier
        self.pattern = pattern
        self.title = title
        self.source = source
        self.score = 0
        self.feedback = []
        
    def __enter__(self):
        return self.source
    
    def __exit__(self, type_, value, traceback):
        self.feedback.insert(0, '#' * len(self.title))
        self.feedback.insert(0, self.title)
        self.feedback.insert(0, '#' * len(self.title))

