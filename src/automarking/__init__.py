"""
#################################
:mod:`automarking` -- Automarking
#################################

Provides the :func:`~automarking.mark` function that takes a :class:`~automarking.core.BlackboardDataSource`
and returns all the :class:`~automarking.core.SubmissionPart`\ s that have been identified from the
:class:`~automarking.core.SubmissionSpec`\ s passed to the :class:`~automarking.core.BlackboardDataSource`.

.. moduleauthor:: Mark Hall <mark.hall@work.room3b.eu>
"""
from .core import BlackboardDataSource, SubmissionSpec


def mark(source):
    """Takes a :class:`~automarking.core.BlackboardDataSource` and iteratively yields each of the
    :class:`~automarking.core.SubmissionPart`\ s extracted from the :class:`~automarking.core.BlackboardDataSource`.
    In each iteration it yields a tuple (:class:`~automarking.core.SubmissionPart`, (filename, filedata)). If
    a student's :class:`~automarking.core.Submission` does not contain any data, then the inner tuple will be
    ``None``.

    The function acts as a generator and can thus be used in ``for`` loops.

    :param source: The data source to load :class:`~automarking.core.SubmissionPart`\ s from.
    :type source: :class:`~automarking.core.BlackboardDataSource`
    """ 
    with source as submissions:
        for submission in submissions:
            with submission as parts:
                for part in parts:
                    with part as data:
                        yield (part, data)
