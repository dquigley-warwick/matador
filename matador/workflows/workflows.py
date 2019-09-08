# coding: utf-8
# Distributed under the terms of the MIT License.

""" This module implements various workflows, ways
of chaining up different calculations at high-throughput.

"""

import abc
import logging
from matador.utils.print_utils import dumps

LOG = logging.getLogger('run3')


class Workflow:
    """ Workflow objects are bundles of calculations defined as
    :obj:`WorkflowStep` objects. Each :obj:`WorkflowStep` takes three arguments:
    the :obj:`matador.compute.FullRelaxer` object used to run the calculations, the calculation
    parameters (which can be modified by each step), the seed name.
    Any subclass of Workflow must implement `preprocess` and `postprocess`
    methods (even if they just return True).

    Attributes:
        relaxer (:obj:`matador.compute.FullRelaxer`): the object that will be running the computation.
        calc_doc (dict): the interim dictionary of structural and
            calculation parameters.
        seed (str): the root seed for the calculation.
        label (str): the name of the type of the Workflow object.
        success (bool): the status of the workflow. This is only set to True after
            final step completes, but BEFORE post-processing.
        steps (:obj:`list` of :obj:`WorkflowStep`): list of steps to be
            completed.

    """
    def __init__(self, relaxer, calc_doc, seed, **workflow_kwargs):
        """ Initialise the Workflow object from a :obj:`matador.compute.FullRelaxer`, calculation
        parameters and the seed name.

        Parameters:
            relaxer (:obj:`matador.compute.FullRelaxer`): the object that will be running the computation.
            calc_doc (dict): dictionary of structure and calculation
                parameters.
            seed (str): root seed for the calculation.

        Raises:
            RuntimeError: if any part of the calculation fails.

        """
        self.relaxer = relaxer
        self.calc_doc = calc_doc
        self.seed = seed
        self.label = self.__class__.__name__
        self.success = None
        self.steps = []

        LOG.info('Performing Workflow of type {} on {}'.format(self.label, self.seed))

        self.preprocess()
        try:
            self.run_steps()
        except RuntimeError as exc:
            LOG.critical('Workflow failed: calling postprocess()')
            self.postprocess()
            raise exc

        self.postprocess()

    @abc.abstractmethod
    def preprocess(self):
        """ This function is run at the start of the workflow, and is
        responsible for adding WorkflowStep objects to the Workflow.

        """
        raise NotImplementedError('Please implement a preprocess method.')

    def postprocess(self):
        """ This function is run upon successful completion of all steps
        of the workflow and is responsible for cleaning up files and any
        other post-processing.

        """
        if self.success:
            LOG.info('Writing results of Workflow {} run to res file and tidying up.'.format(self.label))
            self.relaxer.mv_to_completed(self.seed, keep=True)
        else:
            LOG.info('Writing results of failed Workflow {} run to res file and tidying up.'.format(self.label))
            self.relaxer.mv_to_bad(self.seed)

    def add_step(self, function, name, input_exts=None, output_exts=None, **func_kwargs):
        """ Add a step to the workflow.

        Parameters:
            function (Function): the function to run in the step; must
                accept arguments of (self.relaxer, self.calc_doc, self.seed).
            name (str): the desired name for the step (human-readable).
            func_kwargs (dict): any arguments to pass to function when called.

        """
        self.steps.append(WorkflowStep(function, name,
                                       input_exts, output_exts,
                                       **func_kwargs))

    def run_steps(self):
        """ Loop over steps and run them. """
        try:
            if not self.steps:
                msg = 'No steps added to Workflow!'
                LOG.error(msg)
                raise RuntimeError(msg)

            for step in self.steps:
                LOG.info("Running step {step.name}: {step.function}".format(step=step))
                LOG.debug("Current state: \n" + dumps(self.calc_doc, indent=2))
                step.run_step(self.relaxer, self.calc_doc, self.seed)

            self.success = True

        except RuntimeError:
            self.success = False
            msg = '{} workflow exiting...'.format(self.label)
            LOG.error(msg)
            raise RuntimeError(msg)


class WorkflowStep:
    """ An individual step in a Workflow, defined by a Python function
    and a name. The function will be called with arguments
    (relaxer, calc_doc, seed) with the run_step method.

    Attributes:
        function (function): the function to call.
        name (str): the human-readable name of the step.
        func_kwargs (dict): any extra kwargs to pass to the function.
        input_exts (list): list of input file extensions to cache after running.
        output_exts (list): list of output file extensions to cache after running.

    """
    def __init__(self, function, name, input_exts=None, output_exts=None, **func_kwargs):
        """ Construct a WorkflowStep from a function. """
        LOG.debug('Constructing WorkflowStep: {}'.format(name))
        self.function = function
        self.name = name
        self.func_kwargs = func_kwargs
        self.input_exts = input_exts
        self.output_exts = output_exts

    def _cache_files(self, seed, exts, mode):
        """ Copy any files <seed>.<ext> for ext in exts to
        <seed>.<ext>_<label>.

        Parameters:
            seed (str): seed for the workflow step.
            exts (:obj:`list` of :obj:`str`): list of file extensions, including '.'.
            mode (str): either 'in' (warning printed if file missing) or 'out' (no warning).

        """
        import shutil
        import os
        import glob
        for ext in exts:
            if '*' in ext:
                srcs = glob.glob('{}{}'.format(seed, ext))
            else:
                srcs = ['{}{}'.format(seed, ext)]
            print(ext, srcs)
            for src in srcs:
                dst = src + '_{}'.format(self.name)
                if os.path.isfile(src):
                    shutil.copy2(src, dst, follow_symlinks=True)
                    LOG.info('Backed up {} file {} to {}.'.format(mode, src, dst))
                else:
                    if mode == 'in':
                        error = 'Failed to cache input file {} for step {}.'.format(src, self.name)
                        LOG.warning(error)

    def _cache_inputs(self, seed):
        """ Save any input files for the WorkflowStep with appropriate suffix
        as determined by the WorkflowStep label. All files with <seed>.<ext>
        will be moved to <seed>.<ext>_<name>, for any <ext> inside the
        `input_exts` attribute. This is called after the WorkflowStep has
        finished, even if it does not succeed...

        Parameters:
            seed (str): seed for the workflow step.

        """
        if self.input_exts is not None:
            self._cache_files(seed, self.input_exts, 'in')

    def _cache_outputs(self, seed):
        """ Save any output files for the WorkflowStep with appropriate suffix
        as determined by the WorkflowStep label. All files with <seed>.<ext>
        will be moved to <seed>.<ext>_<name>, for any <ext> inside the
        `output_exts` attribute.

        Parameters:
            seed (str): seed for the workflow step.

        """
        if self.output_exts is not None:
            self._cache_files(seed, self.output_exts, 'out')

    def cache_files(self, seed):
        """ Wrapper for calling both _cache_inputs and _cache_outputs, without
        throwing any errors.
        """
        # try:
        self._cache_inputs(seed)
        self._cache_outputs(seed)
        # except Exception:
            # pass

    def run_step(self, relaxer, calc_doc, seed):
        """ Run the workflow step.

        Parameters:
            relaxer (:obj:`matador.compute.FullRelaxer`): the object that will be running the computation.
            calc_doc (dict): dictionary of structure and calculation
                parameters.
            seed (str): root seed for the calculation.

        Raises:
            RuntimeError: if any step fails.

        """
        try:
            LOG.info('WorkflowStep {} starting...'.format(self.name))
            success = self.function(relaxer, calc_doc, seed, **self.func_kwargs)
        except RuntimeError as exc:
            msg = 'WorkflowStep {} failed with error {}.'.format(self.name, exc)
            LOG.error(msg)
            success = False
            self.cache_files(seed)
            raise exc

        if success is None:
            LOG.info('WorkflowStep {} skipped, did you provide all the input files?'.format(self.name))
            return success

        if success:
            LOG.info('WorkflowStep {} completed successfully.'.format(self.name))
        else:
            LOG.warning('WorkflowStep {} was unsuccessful.'.format(self.name))

        self.cache_files(seed)

        return success
