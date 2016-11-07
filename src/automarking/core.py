# -*- coding: utf-8 -*-
"""
###################################################
:mod:`automarking.core` -- Core Automarking Classes
###################################################

The main classes are the :class:`~automarking.core.SubmissionSpec`, used for
specifying the files to extract, and the :class:`~automarking.core.BlackboardDataSource`
that loads data from the files downloaded from by Blackboard. 

.. moduleauthor:: Mark Hall <mark.hall@work.room3b.eu>
"""
import os
import re
import tarfile

from csv import DictReader, DictWriter
from io import BytesIO
from rarfile import RarFile, BadRarFile, NotRarFile
from zipfile import ZipFile, BadZipFile

STUDENTNR = re.compile(r'[0-9]{8,9}')


class SubmissionSpec(object):
    """The :class:`~core.automarking.SubmissionSpec` is used in the user scripts
    to specify which files to extract from each student's submission.""" 

    def __init__(self, identifier, title, pattern):
        """:param identifier: Identifier to use
        :param title: Title of the submission, which will be used to label feedback
                      in the mark / feedback output
        :type title: ``unicode``
        :param pattern: The regular expression pattern to apply to the filename. Can
                        either be a single regular expression or a ``list`` of
                        regular expressions, in which case at least one of those
                        must match.
        :type pattern: RegExp or ``list`` of RegExp
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
        :rtype: ``boolean``
        """
        if isinstance(self.pattern, list):
            for pattern in self.pattern:
                if re.search(pattern, filename):
                    return True
            return False
        else:
            return re.search(self.pattern, filename)


class BlackboardDataSource(object):
    """The :class:`~automarking.core.BlackboardDataSource` handles loading the
    student submissions from a Blackboard download for offline marking."""

    def __init__(self, gradebook, gradecolumn, specs, options=None):
        """:param gradebook:
        :type gradebook:
        :param gradecolumn:
        :type gradecolumn:
        :param specs:
        :type specs: :py:class:`list`
        :param options:
        :type options:"""
        self.gradebook_filename = gradebook
        self.gradecolumn_filename = gradecolumn
        self.specs = specs
        self.options = options if options is not None else {}

    def __enter__(self):
        if os.path.isdir('tmp'):
            for root, dirs, files in os.walk('tmp', topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
        else:
            os.mkdir('tmp')
        studentlist = []
        with open(self.gradecolumn_filename, encoding='utf-8-sig') as in_f:
            reader = DictReader(in_f)
            for line in reader:
                studentlist.append(line['Student ID'])
        submissions = []
        with ZipFile(self.gradebook_filename) as in_f:
            for studentnr in studentlist:
                submitted = False
                for filename in in_f.namelist():
                    if studentnr in filename:
                        target_filename = 'tmp/%s%s' % (studentnr, filename[filename.find('.'):])
                        if filename.lower().endswith('.tar.bz2') or filename.endswith('.tar.gz'):
                            with in_f.open(filename) as submission_file:
                                with open(target_filename, 'wb') as out_f:
                                    out_f.write(submission_file.read())
                            submissions.append(TarSubmission(studentnr, self.specs, target_filename))
                            submitted = True
                        elif filename.lower().endswith('.zip'):
                            with in_f.open(filename) as submission_file:
                                with open(target_filename, 'wb') as out_f:
                                    out_f.write(submission_file.read())
                            submissions.append(ZipSubmission(studentnr, self.specs, target_filename))
                            submitted = True
                        elif filename.lower().endswith('.rar'):
                            with in_f.open(filename) as submission_file:
                                with open(target_filename, 'wb') as out_f:
                                    out_f.write(submission_file.read())
                            submissions.append(RarSubmission(studentnr, self.specs, target_filename))
                            submitted = True
                        elif filename.endswith('.txt'):
                            pass
                        else:
                            submissions.append(MissingSubmission(studentnr, self.specs, message='Unknown submission type %s' % filename[filename.rfind('.'):]))
                            submitted = True
                if not submitted:
                    submissions.append(MissingSubmission(studentnr, self.specs, message=self.options['no_submission_message'] if 'no_submission_message' in self.options else 'No submission'))
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
        self.parts = []
        self.feedback = []

    def __enter__(self):
        return self.parts

    def __exit__(self, type_, value, traceback):
        self.score = 0
        for part in self.parts:
            self.score = self.score + part.score
            self.feedback.extend(part.feedback)


class MissingSubmission(Submission):

    def __init__(self, studentnr, specs, message):
        Submission.__init__(self, studentnr)
        self.feedback.append(message)


class TarSubmission(Submission):

    def __init__(self, studentnr, specs, source_filename):
        Submission.__init__(self, studentnr)
        try:
            source_file = tarfile.open(source_filename)
            for spec in specs:
                part = SubmissionPart(spec)
                self.parts.append(part)
                for filename in source_file.getnames():
                    if spec.matches(filename):
                        part.add_data(filename, source_file.extractfile(filename).read())
        except tarfile.TarError:
            pass


class ZipSubmission(Submission):

    def __init__(self, studentnr, specs, source_filename):
        Submission.__init__(self, studentnr)
        try:
            source_file = ZipFile(source_filename)
            for spec in specs:
                part = SubmissionPart(spec)
                self.parts.append(part)
                for filename in source_file.namelist():
                    if spec.matches(filename):
                        part.add_data(filename, source_file.open(filename).read())
        except BadZipFile:
            pass


class RarSubmission(Submission):

    def __init__(self, studentnr, specs, source_filename):
        Submission.__init__(self, studentnr)
        try:
            source_file = RarFile(source_filename)
            for spec in specs:
                part = SubmissionPart(spec)
                self.parts.append(part)
                for filename in source_file.namelist():
                    filename = filename.replace('\\', '/')
                    if spec.matches(filename):
                        part.add_data(filename, source_file.open(filename).read())
        except BadRarFile:
            pass
        except NotRarFile:
            pass


class SubmissionPart(object):

    def __init__(self, spec):
        self.spec = spec
        self.data = None
        self.score = 0
        self.feedback = []

    def add_data(self, filename, data):
        if self.data is None:
            self.data = (filename, BytesIO(data))
        elif isinstance(self.data, tuple):
            self.data = [self.data, (filename, BytesIO(data))]
        else:
            self.data.append((filename, BytesIO(data)))

    def __enter__(self):
        return self.data

    def __exit__(self, type_, value, traceback):
        self.feedback.insert(0, '#' * len(self.spec.title))
        self.feedback.insert(0, self.spec.title)
        self.feedback.insert(0, '#' * len(self.spec.title))
