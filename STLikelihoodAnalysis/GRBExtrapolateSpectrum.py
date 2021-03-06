#!/usr/bin/env python
#!/usr/bin/env python
"""Module for LAT likelihood analysis chain of pLATLikelihoodConfig.py.
"""
import sys
import os
import os.path
import logging
import pickle
import datetime
import numpy as np
import math
from math import log10, log, sqrt, ceil, isnan, pi, factorial
from sympy import *
from scipy import integrate
import click
import matplotlib as mpl
import matplotlib.pyplot as plt
import pLATLikelihoodConfig
#import pLATLikelihoodChain
from STLikelihoodAnalysis import get_module_logger

##### Logger #####
logger = get_module_logger(__name__)


##### Functions for TS calculation #####
def compute_GPoisson(x, m, s, n):
    return pow(x,n)* ( exp(-pow(x-m,2)/2./pow(s,2)-x) + int(n==0)*exp(-pow(x+m,2)/2./pow(s,2)) ) /sqrt(2.*pi)/s


##### Analysis Chain Class #####
class GRBExtrapolateSpectrum():
    def __init__(self, name, phase, emin_fitted, emax_fitted, emin_extrapolated, emax_extrapolated, tstop=10000., deg_roi=12., zmax=100., suffix='', grbcatalogue=pLATLikelihoodConfig.GRB_CATALOGUE_LTF, path_pickle=None):

        # Target GRB
        grb = pLATLikelihoodConfig.GRBTarget(name, grbcatalogue)

        # Energy setups
        self.emin_fitted = emin_fitted
        self.emax_fitted = emax_fitted
        logger.info('Energy range for fitting: {emin} - {emax}'.format(emin=self.emin_fitted, emax=self.emax_fitted))
        self.emin_extrapolated = emin_extrapolated
        self.emax_extrapolated = emax_extrapolated
        logger.info('Energy range for extrapolation: {emin} - {emax}'.format(emin=self.emin_extrapolated, emax=self.emax_extrapolated))
        #self.energybins = []

        # Analysis instance
        self.analysis_fit = pLATLikelihoodConfig.GRBConfig(target=grb, phase=phase, tstop=tstop, emin=self.emin_fitted, emax=self.emax_fitted, deg_roi=deg_roi, zmax=zmax, suffix=suffix)

        emin_whole = min(self.emin_fitted, self.emin_extrapolated)
        emax_whole = max(self.emax_fitted, self.emax_extrapolated)
        self.analysis_extrapolated = pLATLikelihoodConfig.GRBConfig(target=grb, phase=phase, tstop=tstop, emin=emin_whole, emax=emax_whole, deg_roi=deg_roi, zmax=zmax, suffix=suffix)

        # Summary
        self.dct_summary = {'datetime':datetime.datetime.today().strftime("%Y/%m/%d %H:%M:%S"), 'target':str(name), 'lower_energies':{'emin':self.emin_fitted, 'emax':self.emax_fitted}, 'highest_energies':{'emin':self.emin_extrapolated, 'emax':self.emax_extrapolated}, 'whole_energies':{'emin':emin_whole, 'emax':emax_whole}, 'phase':phase, 'tstart': self.analysis_fit.tmin, 'tstart':self.analysis_fit.tmax, 'roi':deg_roi, 'zmax':zmax}

        # Pickle
        if pickle==None:
            self.path_pickle = './Summary_{name}_{phase}{suffix}.pickle'.format(name=name, phase=mode, suffix=suffix if suffix=='' else '_'+suffix)

        self.path_pickle = path_pickle


    # def __getstate__(self):
    #     state = self.__dict__.copy()
    #     del state['like', 'likeobj']
    #     return state


    # def __setstate__(self, state):
    #     self.__dict__.update(state)


    def setup_fit(self):
        self.analysis_fit.setup()


    def setup_extrapolate(self):
        self.analysis_extrapolated.set_directories()
        self.analysis_extrapolated.download()
        self.analysis_extrapolated.filter()
        self.analysis_extrapolated.maketime()
        self.analysis_extrapolated.livetime()
        self.analysis_extrapolated.exposure()
        logger.debug('Path of reffered model: {0}'.format(self.analysis_fit.path_model_xml_new))
        self.analysis_extrapolated.use_external_model(self.analysis_fit.path_model_xml_new)
        self.analysis_extrapolated.diffuse_responses()
        

#    def fit(self, redo=True):
#        self.analysis_fit.fit(bredo=redo)


#    def fit_whole(self, redo=True):
#        self.analysis_extrapolated.fit(bredo=redo)


    def set_likelihood_extrapolate(self):
        self.analysis_extrapolated.set_likelihood()
        #for i in range(self.analysis_extrapolated.like.nFreeParams()):
        #    self.analysis_extrapolated.like.freeze(i)

        # Energy bins
        self.ebins = self.analysis_extrapolated.like.energies
        self.nebins = len(self.ebins)-1


    def plot_extrapolated_count_spectrum(self):
        self.analysis_extrapolated.plot_countspectra_fitted()


    def plot_error(self):
        x_cspec_fit = (self.analysis_extrapolated.like.energies[:-1] + self.analysis_extrapolated.like.energies[1:])/2.
        logger.debug(x_cspec_fit)
        # Model count
        y_model_all, y_model_target, y_model_others = self.analysis_extrapolated.count_axes()

        # Eval error
        y_model_err = np.zeros_like(y_model_all)
        for ie in range(self.nebins):
            flux, flux_err = self.analysis_fit.eval_flux_and_error(emin=self.ebins[ie], emax=self.ebins[ie+1])
            flux_frac_err = flux_err / flux
            y_model_err[ie] = y_model_target[ie] * flux_frac_err
            logger.debug("""Energy: {0}, Flux = {1} +/- {2}""".format(x_cspec_fit[ie], flux, flux_err))

        fig, axes = self.analysis_extrapolated.plot_countspectra_fitted()
        logger.debug(fig)
        axes[0].fill_between(x_cspec_fit, y_model_all+y_model_err, y_model_all-y_model_err, alpha=0.2, color='b', label='Fitting uncertainty')
        fig.savefig("{0}/Extrapolated_count_spectrum_{1}{2}.png".format(self.analysis_extrapolated.dir_work, self.analysis_extrapolated.target.name, self.analysis_extrapolated.suffix))


    def eval_deviation(self):
        """Eval deviation in a certain energy range from
"""
        #x_cspec_fit = (self.analysis_extrapolated.like.energies[:-1] + self.analysis_extrapolated.like.energies[1:])/2.
        nemin_eval = -1
        nemax_eval = -1
        logger.debug('Energy bins: {0}'.format(self.ebins))
        diff_energy_edge_lo = sys.maxsize
        diff_energy_edge_hi = sys.maxsize
        for ie in range(self.nebins):
            if abs(self.ebins[ie]-self.emin_extrapolated) < diff_energy_edge_lo:
                diff_energy_edge_lo = abs(self.ebins[ie]-self.emin_extrapolated)
                nemin_eval = ie
            if abs(self.ebins[ie+1]-self.emax_extrapolated) < diff_energy_edge_hi:
                diff_energy_edge_hi = abs(self.ebins[ie+1]-self.emax_extrapolated)
                nemax_eval = ie

            # if self.ebins[ie]<=self.emin_extrapolated and self.ebins[min(self.nebins, ie+1)]>self.emin_extrapolated:
            #     nemin_eval = ie
            # if self.ebins[ie]<self.emax_extrapolated and self.ebins[min(self.nebins,ie+1)]>=self.emax_extrapolated:
            #     nemax_eval = ie
        emin_eval = self.ebins[nemin_eval]
        emax_eval = self.ebins[nemax_eval+1]
        if emin_eval!=self.emin_extrapolated:
            self.emin_extrapolated = emin_eval
            logger.warning('Minimum evaluation energy has changed to {0} MeV!'.format(emin_eval))
        if emax_eval!=self.emax_extrapolated:
            self.emax_extrapolated = emax_eval
            logger.warning('Maxmum evaluation energy has changed to {0} MeV!'.format(emax_eval))

        # Observed count
        nobs = sum(self.analysis_extrapolated.like._Nobs()[nemin_eval:nemax_eval+1])
        self.dct_summary['highest_energies']['nobs'] = nobs
        logger.info('Observed count in {emin} - {emax}: {nobs}'.format(emin=emin_eval, emax=emax_eval, nobs=nobs))
        # Predicted count
        y_model_all, y_model_target, y_model_others = self.analysis_extrapolated.count_axes()
        npred_all = sum(y_model_all[nemin_eval:nemax_eval+1])
        npred_target = sum(y_model_target[nemin_eval:nemax_eval+1])
        npred_others = sum(y_model_others[nemin_eval:nemax_eval+1])
        # Predicted error
        flux, flux_err = self.analysis_fit.eval_flux_and_error(emin=self.ebins[nemin_eval], emax=self.ebins[nemax_eval+1])
        flux_frac_err = flux_err / flux
        npred_target_err = npred_target*flux_frac_err
        logger.info('Predicted count in {emin} - {emax}: {npred} +/- {npred_err}'.format(emin=emin_eval, emax=emax_eval, npred=npred_all, npred_err=npred_target_err))

        self.dct_summary['highest_energies']['npred_all'] = {'value':npred_all}
        self.dct_summary['highest_energies']['npred_target'] = {'value':npred_target, 'error':npred_target_err}
        self.dct_summary['highest_energies']['npred_others'] = {'value':npred_others}

        eref_hiend = sqrt(emin_eval*emax_eval)
        # Calc tentative uncertainty of observed count for TS evaluation
        # Find Index parameter
        freeParValues = []
        for sourcename in self.analysis_fit.like.sourceNames():
            for element in self.analysis_fit.like.freePars(sourcename):
                freeParValues.append(element.getValue())
        g_index = freeParValues.index(self.analysis_fit.like.freePars(self.analysis_fit.target.name)[1].getValue())
        # Covariance for index and itself
        cov_gg = self.analysis_fit.like.covariance[g_index][g_index]
        nobs_sigma_factor = sqrt(pow(flux_frac_err,2) + pow(nobs/npred_all*(log10(eref_hiend)-log10(self.analysis_fit.like.model[self.analysis_fit.target.name].funcs['Spectrum'].getParam('Scale').value())) ,2) * cov_gg)
        nobs_sigma = npred_all * nobs_sigma_factor
        logger.info('Tentative uncertainty of observed count ({0}): {1}'.format(nobs, nobs_sigma))
        npred_sigma_factor = sqrt(pow(flux_frac_err,2) + pow((log10(eref_hiend)-log10(self.analysis_fit.like.model[self.analysis_fit.target.name].funcs['Spectrum'].getParam('Scale').value())) ,2) * cov_gg)
        npred_sigma = npred_target * npred_sigma_factor
        logger.info('Check of uncertainty of predicted count ({0}): {1}'.format(npred_all, npred_sigma))

        # Use simpy
        # Predicted
        (integral_PGauss_mu, integral_PGauss_mu_err)  = integrate.quad(compute_GPoisson, 0, npred_all+5.*npred_target_err, args=(npred_all, npred_target_err, nobs))
        logger.info('Integral of modified Gaussian : {0} +/- {1}:'.format(integral_PGauss_mu, integral_PGauss_mu_err))
        if integral_PGauss_mu<=0:
            logger.warning("""Integral for model is NOT positive!!!
{0}""".format(integral_PGauss_mu))
            integral_PGauss_mu = 0.001
        if integral_PGauss_mu_err>integral_PGauss_mu/100.:
            logger.warning("""Uncertainty of integration for model is very large!!!
{0} +/- {1}""".format(integral_PGauss_mu, integral_PGauss_mu_err))
            integral_PGauss_mu = 0.001
        # Observed
        if nobs>0:
            (integral_PGauss_n, integral_PGauss_n_err)  = integrate.quad(compute_GPoisson, 0, nobs+5.*nobs*flux_frac_err, args=(nobs, nobs_sigma, nobs))
        else:
            (integral_PGauss_n, integral_PGauss_n_err)  = (1, 0)
        logger.info('Integral of modified Gaussian for mu=n : {0} +/- {1}'.format(integral_PGauss_n, integral_PGauss_n_err))
        if integral_PGauss_n_err>integral_PGauss_n/100.:
            logger.warning("""Uncertainty of integration for observation is very large!!!
{0} +/- {1}""".format(integral_PGauss_mu, integral_PGauss_mu_err))
        deviation = 2. * ( log(integral_PGauss_n / integral_PGauss_mu) )
        sign_deviation = int(nobs>=npred_all)*2-1
        logger.info('{sign} deviation: TS={ts}'.format(sign='Positive' if sign_deviation>=0 else 'Negative', ts=deviation))
        return sign_deviation*deviation

    def summarize_powerlaw_fit_results(self, analysis, key_edomain):
        logger.debug(self.dct_summary)
        if not key_edomain in self.dct_summary:
            self.dct_summary[key_edomain] = {}
        # Model parameters
        for name_param in ('Prefactor', 'Index', 'Scale'):
            param = analysis.like.model[analysis.target.name].funcs['Spectrum'].getParam(name_param)
            self.dct_summary[key_edomain][name_param] = {'value':param.value(), 'error':param.error()}

        # Flux
        flux_and_err = analysis.eval_flux_and_error(analysis.target.name) #, emin_extrapolated, emax_extrapolated)
        self.dct_summary[key_edomain]['flux'] = {'value':flux_and_err[0], 'error':flux_and_err[1]}

        # TS
        name = analysis.target.name
        logger.debug('TS of {0}:'.format(name))
        self.dct_summary[key_edomain]['TS'] = analysis.like.Ts(str(name))
        logger.debug(self.dct_summary)

        # Detailed limits on flux, eflux, dnde, e2dnde
        logger.info('Evaluation of detailed parameter limits is starting...')


    def pickle(self, obj):
        if self.path_pickle is not None:
            logger.info("""Object contents: 
{0}""".format(obj))
            with open(self.path_pickle, mode='wb') as f:
                pickle.dump(obj, f)
            logger.info('Result summary has been saved as {0}'.format(self.path_pickle))


##### Called by main function #####

def extrapolate_spectrum(name, mode, emin_fitted, emax_fitted, emin_extrapolated, emax_extrapolated, deg_roi, zmax, suffix, grbcatalogue, brefit, pickle):

    chain = GRBExtrapolateSpectrum(name=name, phase=mode, emin_fitted=emin_fitted, emax_fitted=emax_fitted, emin_extrapolated=emin_extrapolated, emax_extrapolated=emax_extrapolated, tstop=10000., deg_roi=deg_roi, zmax=zmax, suffix=suffix, grbcatalogue=grbcatalogue, path_pickle=pickle)

    # Fitting
    chain.setup_fit()
    chain.analysis_fit.fit(bredo=brefit)
    chain.summarize_powerlaw_fit_results(chain.analysis_fit, 'lower_energies')

    # Extrapolating
    chain.setup_extrapolate()
    chain.set_likelihood_extrapolate()
    chain.plot_error()

    chain.dct_summary['highest_energies']['emin'] = chain.emin_extrapolated
    chain.dct_summary['highest_energies']['emax'] = chain.emax_extrapolated

    # Deriving deviation
    deviation_signed = chain.eval_deviation()
    chain.dct_summary['deviation_ts'] = deviation_signed

    # Fitting in whole energy range
    chain.analysis_extrapolated.fit(bredo=brefit)
    chain.summarize_powerlaw_fit_results(chain.analysis_extrapolated, 'whole_energies')

    flux_and_err_highest_energies = chain.analysis_extrapolated.eval_flux_and_error(chain.analysis_extrapolated.target.name, chain.emin_extrapolated, chain.emax_extrapolated)
    chain.dct_summary['highest_energies']['flux'] = {'value':flux_and_err_highest_energies[0], 'error':flux_and_err_highest_energies[1]}

    # Detailed limits of flux, eflux, dnde, e2dnde
    chain.dct_summary['whole_energies']['limits'] = chain.analysis_extrapolated.eval_limits_powerlaw()
    chain.dct_summary['lower_energies']['limits'] = chain.analysis_fit.eval_limits_powerlaw()

    # Pickle
    chain.pickle(chain.dct_summary)

#class GRBExtrapolateSpectrumResults():
#    def __init__(self):
        

@click.command()
@click.argument('name', type=str)
@click.option('--eminfit', type=float, default=100.)
@click.option('--emaxfit', type=float, default=5623.41)
@click.option('--eminextrapolate', type=float, default=10000.)
@click.option('--emaxextrapolate', type=float, default=100000.)
@click.option('--roi', type=float, default=7.)
@click.option('--zmax', type=float, default=100.)
@click.option('--suffix', type=str, default='')
@click.option('--grbcatalogue', type=str, default=pLATLikelihoodConfig.GRB_CATALOGUE_LTF)
@click.option('--mode', '-m', type=click.Choice(['unified', 'prompt', 'afterglow', 'earlyAG', 'lateAG', 'lightcurve', 'special']))
@click.option('--refit', '-r', is_flag=True)
@click.option('--pickle', '-p', type=str, default=None)
def main(name, mode, eminfit, emaxfit, eminextrapolate, emaxextrapolate, roi, zmax, suffix, grbcatalogue, refit, pickle):
    extrapolate_spectrum(name, mode, eminfit, emaxfit, eminextrapolate, emaxextrapolate, roi, zmax, suffix, grbcatalogue, refit, pickle)


if __name__ == '__main__':
    main()
