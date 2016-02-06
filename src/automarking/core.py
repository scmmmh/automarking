# -*- coding: utf-8 -*-
"""
###################################################
:mod:`automarking.core` -- Core Automarking Classes
###################################################

The main classes are the :class:`~automarking.core.SubmissionSpec`, used for
specifying the files to extract, and the :class:`~automarking.core.BlackboardDataSource`
that is the main entry point into the automarking functionality.

.. moduleauthor:: Mark Hall <mark.hall@work.room3b.eu>
"""
import re
import tarfile

from csv import DictReader, DictWriter
from os import path
from rarfile import RarFile, BadRarFile
from zipfile import ZipFile, BadZipFile

STUDENTNR = re.compile(r'[0-9]{8,9}')


class SubmissionSpec(object):
    """The :class:`~core.automarking.SubmissionSpec` is used in the user scripts
    to specify which files to extract from each student's submission.""" 

    def __init__(self, identifier, title, pattern):
        """Create a new :class:`~core.automarking.SubmissionSpec`.

        :param identifier: Identifier to use
        :param title: Title of the submission, which will be used to label feedback
                      in the mark / feedback output
        :type title: ``unicode``
        :param pattern: The pattern to apply to the path. If a single ``unicode`` is
                        passed, then the regexp is applied only to the
                        ``os.path.basename`` of the submission filename. If a ``list``
                        is passed, then the filename is split at the path separator
                        and then each element of the pattern is applied to each element
                        of the filename and only if all elements match does the
                        :class:`~core.automarking.SubmissionSpec` match
        :type pattern: Either a ``unicode`` regexp or a ``list`` of ``unicode`` regexps
        """
        self.identifier = identifier
        self.title = title
        self.pattern = pattern

    def matches(self, filename):
        """Test whether the ``filename`` is matched by this
        :class:`~automarking.core.SubmissionSpec`.

        :param filename: The filename to check
        :type filename: ``unicode``
        :return: ``True`` if the ``filename`` is matched, ``False`` otherwise
        :return_type: ``boolean``
        """
        if isinstance(self.pattern, list):
            filename = filename.split('/')
            if len(filename) == len(self.pattern):
                for filepart, pattern in zip(filename, self.pattern):
                    if not re.search(pattern, filepart):
                        return False
                return True
        else:
            return re.search(self.pattern, path.basename(filename))
        return False


class BlackboardDataSource(object):
    
    def __init__(self, gradebook, gradecolumn, specs):
        self.gradebook_filename = gradebook
        self.gradecolumn_filename = gradecolumn
        self.specs = specs
    
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
                        submissions.append(TarSubmission(match.group(0), self.specs, target_filename))
                    elif filename.lower().endswith('.zip'):
                        with in_f.open(filename) as submission_file:
                            with open(target_filename, 'wb') as out_f:
                                out_f.write(submission_file.read())
                        submissions.append(ZipSubmission(match.group(0), self.specs, target_filename))
                    elif filename.lower().endswith('.rar'):
                        with in_f.open(filename) as submission_file:
                            with open(target_filename, 'wb') as out_f:
                                out_f.write(submission_file.read())
                        submissions.append(RarSubmission(match.group(0), self.specs, target_filename))
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
    
    def __init__(self, studentnr, specs, source_filename):
        Submission.__init__(self, studentnr)
        try:
            source_file = tarfile.open(source_filename)
            for spec in specs:
                for filename in source_file.getnames():
                    if spec.matches(filename):
                        self.files.append(SubmissionFile(spec, source_file.extractfile(filename), path.basename(filename)))
        except tarfile.TarError:
            pass


class ZipSubmission(Submission):

    def __init__(self, studentnr, specs, source_filename):
        Submission.__init__(self, studentnr)
        try:
            source_file = ZipFile(source_filename)
            for spec in specs:
                for filename in source_file.namelist():
                    if spec.matches(filename):
                        self.files.append(SubmissionFile(spec, source_file.open(filename), path.basename(filename)))
        except BadZipFile:
            pass


class RarSubmission(Submission):

    def __init__(self, studentnr, specs, source_filename):
        Submission.__init__(self, studentnr)
        try:
            source_file = RarFile(source_filename)
            for spec in specs:
                for filename in source_file.namelist():
                    filename = filename.replace('\\', '/')
                    if spec.matches(filename):
                        self.files.append(SubmissionFile(spec, source_file.open(filename), path.basename(filename)))
        except BadRarFile:
            pass


class SubmissionFile(object):
    
    def __init__(self, spec, source, filename):
        self.spec = spec
        self.source = source
        self.score = 0
        self.feedback = []
        self.filename = filename
        
    def __enter__(self):
        return self.source
    
    def __exit__(self, type_, value, traceback):
        self.feedback.insert(0, '#' * len(self.spec.title))
        self.feedback.insert(0, self.spec.title)
        self.feedback.insert(0, '#' * len(self.spec.title))
