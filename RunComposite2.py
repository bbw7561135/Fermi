#!/usr/bin/env python

import sys
import os
import os.path
import matplotlib as mpl
#mpl.use('tkagg')
mpl.use('Agg')
import matplotlib.pyplot as plt
#from matplotlib import gridspec
import gt_apps as my_apps
from pyLikelihood import *
from UnbinnedAnalysis import *
from Composite2 import Composite2
from CompositeLikelihood import CompositeLikelihood
#from bdlikeSED import *
import click
from astropy.io import fits
import numpy as np
import ReadLTFCatalogueInfo
from pLsList import ls_list

mpl.rcParams['font.size'] = 25

def judge_category_fluence(tb, name, lst_cut):
    tb = ReadLTFCatalogueInfo.select_gbm_exist(tb)
    tb1 = ReadLTFCatalogueInfo.select_one_by_name(tb, name)
    ncategory = len(lst_cut)
    for ic in range(len(lst_cut)):
        ncategory -= int(tb1['FLUENCE']>=lst_cut[ic])
    print 'Fluence:', tb1['FLUENCE'], '-> Category:', ncategory
    return ncategory


def run_composite2(lst_inputs, path_outdir, names_params_tied_universal=['Index'], names_params_tied_category=['Prefactor'], ncat_analyzed=0, str_suffix=''):
    # Open table
    tb = ReadLTFCatalogueInfo.open_table()
    # Definition of GBM fluence categories
    FLUENCE_CUT = [1.09e-04, 3.06e-05] #[1.45E-4, 3.70E-5] # Top 10%, 35%
    NCATEGORIES_FLUENCE = len(FLUENCE_CUT)+1
    dct_category_fluence = {}
#    rh_fluence_weightNobs = ROOT.TH1D('roohtg', 'GBM Fluence', 100, -7, -2)

    path_base = os.getcwd()
    os.chdir(path_outdir)
    lst_name_subdir = ['plots', 'xml', 'fits']
    for name_subdir in lst_name_subdir:
        path_subdir = '{0}/{1}'.format(path_outdir, name_subdir)
        if not os.path.exists(path_subdir):
            os.makedirs(path_subdir)
    if str_suffix != '':
        str_suffix = '_' + str_suffix
    irfs = 'P8R2_SOURCE_V6' # To be used with P301 data
    optimizer='Minuit'
    level = 2.71
    CompositeLike = Composite2(optimizer=optimizer)
    like={}
    targets = []
    lst_fluence_gbm = []
    lst_fluence_gbm_err = []
    lst_nobs_lat = []
    targets_analyzed = []
    for (itarget, path_target) in enumerate(lst_inputs):
        path_base, name_base = os.path.split(path_target)
        target = name_base[3:12]
        targets.append(target)
        print '##### No.{0} {1} #####'.format(itarget, target)
        dct_category_fluence[target] = judge_category_fluence(tb, target, FLUENCE_CUT) 

        if ncat_analyzed-1 not in (dct_category_fluence[target], -1):
            print 'skipped.'
            continue

        targets_analyzed.append(target)
        ltcube = '/'.join((path_base, name_base+'_ft1_ltCube.fits'))
        expMap = '/'.join((path_base, name_base+'_ft1_expMap.fits'))
        srcModel = '/'.join((path_base, name_base+'_ft1_model.xml'))
        evt = '/'.join((path_base, name_base+'_ft1_filtered.fits'))
        sc = '/'.join((path_base, '../../../../..', name_base.replace('_P8_P302_BASE_T00-999-101000_r030', '_T00-999-101000_ft2-30s.fits')))
        if itarget==0:
            print 'Files of the first target.'
            print '  Event:', evt
            print '  Spacecraft:', sc
            print '  Livetime cube:', ltcube
            print '  Exposure map:', expMap
            print '  Source model:', srcModel

        # Diffuse responses
        my_apps.diffResps['evfile'] = evt
        my_apps.diffResps['scfile'] = sc
        my_apps.diffResps['srcmdl'] = srcModel
        my_apps.diffResps['irfs'] = irfs
        my_apps.diffResps.run()

        like[target] = unbinnedAnalysis(evfile=evt,
                                        scfile=sc,
                                        expmap=expMap,
                                        expcube=ltcube,
                                        irfs=irfs,
                                        srcmdl=srcModel,
                                        optimizer=optimizer)
        for source in like[target].sourceNames():
            if source not in (target):
                like[target].normPar(source).setFree(False)
        sys.stdout.flush()

        CompositeLike.addComponent(like[target])
        sys.stdout.flush()

    for icat in range(NCATEGORIES_FLUENCE):
        if ncat_analyzed-1 not in (icat, -1):
            print 'skipped.'
            continue
        print '======================'
        print '===== Category', icat, '====='
        print '======================'
        print 'Target:', len(targets_analyzed), 'GRBs.'
        for target in targets:
            if dct_category_fluence[target]==icat or ncat_analyzed==0:
                print target,
        print ''

       # Tying parameters for each fluence category separately
        tiedParams_category = {}
        for par in names_params_tied_category:
            tiedParams_category[par] = []
            for target in targets_analyzed:
                tiedParams_category[par].append(tuple([like[target], target, par]))
            CompositeLike.tieParameters(tiedParams_category[par])
        print '* Parameters tied by each category:'
        print tiedParams_category

       # Tying parameters universaly
        tiedParams_universal = {}
        for par in names_params_tied_universal:
            tiedParams_universal[par] = []
            for target in targets_analyzed:
                tiedParams_universal[par].append(tuple([like[target], target, par]))
            CompositeLike.tieParameters(tiedParams_universal[par])
    print '* Parameters tied universaly:'
    print tiedParams_universal

    #minuit = eval("pyLike.%s(CompLike.composite)"%optimizer)
    #minuit.setStrategy(2)
    #likeobj = pyLike.NewMinuit(like.logLike)
    fit_result = CompositeLike.fit(covar=True,tol=1.e-5,optimizer=optimizer)
    print '== Fitting result =='
    print fit_result
    print ''
    #print minuit.getRetCode()

#    gs_stacked = gridspec.GridSpec(2, 1, height_ratios=(2, 1))
    fig_stacked, ax_stacked = plt.subplots(2, 1, figsize=(16, 10))
    x_stacked = (like[targets_analyzed[0]].energies[:-1] + like[targets_analyzed[0]].energies[1:])/2.
    print len(x_stacked), 'energy bins.'
    model_sum_stacked = np.zeros_like(like[targets_analyzed[0]]._srcCnts(like[targets_analyzed[0]].sourceNames()[0]))
    model_grb_stacked = np.zeros_like(model_sum_stacked)
    model_others_stacked = np.zeros_like(model_sum_stacked)
    nobs_sum_stacked = np.zeros_like(model_sum_stacked)

    lst_tops = [{'name':'', 'fluence':0, 'nobs':np.zeros_like(model_sum_stacked)} for x in (1, 2, 3)]

    # Loop over GRBs
    for target in targets_analyzed:
        print target
        ncategory = dct_category_fluence[target]
        print '  Producing plots...'
        sys.stdout.flush()
        path_xml = '{0}/xml/likelihood_status_{1}{2}.xml'.format(path_outdir, target, str_suffix)
        like[target].writeXml(path_xml)
        path_spectra = '{0}/fits/counts_spectra_{1}{2}.fits'.format(path_outdir, target, str_suffix)
        like[target].writeCountsSpectra(path_spectra)
        fspec = fits.open(path_spectra)
        tb_counts = fspec[1].data
        #tb_fluxes = fspec[2].data
        #tb_ebounds = fspec[3].data
        fig, ax = plt.subplots(2, 1, figsize=(16, 10), sharex=True)
        model_sum = np.zeros_like(model_sum_stacked)
        model_grb = np.zeros_like(model_sum_stacked)
        model_others = np.zeros_like(model_sum_stacked)
        nobs_sum = np.zeros_like(model_sum)
        for col_src in tb_counts.columns[1:]:
            model_sum = model_sum + tb_counts[col_src.name]
            model_sum_stacked = model_sum_stacked + tb_counts[col_src.name]
            if col_src.name == target:
                model_grb = model_grb + tb_counts[col_src.name]
                model_grb_stacked = model_grb_stacked + tb_counts[col_src.name]
            else:
                model_others = model_others + tb_counts[col_src.name]
                model_others_stacked = model_others_stacked + tb_counts[col_src.name]

        nobs_sum = tb_counts['ObsCounts']
        lst_nobs_lat.append(sum(nobs_sum))
        tb1 = ReadLTFCatalogueInfo.select_one_by_name(tb, target)
        lst_fluence_gbm.append(tb1["FLUENCE"])
        lst_fluence_gbm_err.append(tb1["FLUENCE_ERROR"])
        #rh_fluence_weightNobs.Fill(np.log10(lst_fluence_gbm[-1]), lst_nobs_lat[-1])

        # Top3 in all categories
        if lst_nobs_lat[-1]>sum(lst_tops[0]['nobs']):
            lst_tops[2] = lst_tops[1]
            lst_tops[1] = lst_tops[0]
            lst_tops[0] = {'name':target, 'fluence':tb1["FLUENCE"], 'nobs':nobs_sum}
        elif lst_nobs_lat[-1]>sum(lst_tops[1]['nobs']):
            lst_tops[2] = lst_tops[1]
            lst_tops[1] = {'name':target, 'fluence':tb1["FLUENCE"], 'nobs':nobs_sum}
        elif lst_nobs_lat[-1]>sum(lst_tops[2]['nobs']):
            lst_tops[2] = {'name':target, 'fluence':tb1["FLUENCE"], 'nobs':nobs_sum}                

        for ihiest in (1, 2, 3, 4):
            if nobs_sum[-ihiest]>0:
                print nobs_sum[-ihiest], 'events in the', ihiest, '-th highest energy bin.'
        nobs_sum_stacked = nobs_sum_stacked + tb_counts['ObsCounts']
        try:
            ax[0].loglog(x_stacked, model_sum, label='Sum of models')
            ax[0].loglog(x_stacked, model_grb, label=target)
            ax[0].loglog(x_stacked, model_others, label='Others')
            ax[0].errorbar(x_stacked, nobs_sum, yerr=np.sqrt(nobs_sum), fmt='o',label='Counts')
            ax[0].legend(loc=1, fontsize=12)
            ax[0].set_ylabel('[counts]')
            ax[0].set_title(target)
            ax[0].set_xticklabels([])
            ax[0].grid(ls='-', lw=0.5, alpha=0.2)
            resid = (nobs_sum - model_sum) / model_sum
            resid_err = np.sqrt(nobs_sum) / model_sum
            ax[1].set_xscale('log')
            ax[1].errorbar(x_stacked, resid, yerr=resid_err, fmt='o')
            ax[1].axhline(0.0,ls=':')
            ax[1].grid(ls='-', lw=0.5, alpha=0.2)
            ax[1].set_xlabel(r'$\log_{10}Energy \rm{[MeV]}$')
            ax[1].set_ylabel('Fractional residual')
            fig.tight_layout()
            fig.subplots_adjust(hspace=0)
            ax[1].set_yticks([y for y in ax[1].get_yticks() if y<ax[1].get_ylim()[1]])

            fig.savefig('{0}/plots/Spectrum{1}{2}.png'.format(path_outdir, target, str_suffix))
            plt.close()
            
        except ValueError:
            continue
        
    # # Histogram of GBM fluence
    # fig2d = plt.figure()
    # ax2d = fig2d.add_axes((0.1, 0.1, 0.8, 0.8))
    # npa_fluence_gbm = np.array(lst_fluence_gbm)
    # npa_fluence_gbm_err = np.array(lst_fluence_gbm_err)
    # npa_nobs_lat = np.array(lst_nobs_lat)
    # ax2d.set_xscale('log')
    # ax2d.set_yscale('log')
    # #ax2d.set_ylim(0.5, 200)
    # ax2d.errorbar(x=npa_fluence_gbm, y=npa_nobs_lat, xerr=npa_fluence_gbm_err, fmt='o')
    # #ax2d.errorbar(x=npa_fluence_gbm, y=npa_nobs_lat, xerr=npa_fluence_gbm_err, yerr=np.sqrt(npa_nobs_lat), fmt='o')
    # ax2d.axvline(FLUENCE_CUT[0],ls=':')
    # ax2d.axvline(FLUENCE_CUT[1],ls=':')
    # ax2d.set_xlabel('Fluence in GBM [erg/cm^{2}]')
    # ax2d.set_ylabel('Photons in LAT [counts]')
    # fig2d.savefig('{0}/plots/nobs_vs_GBMfluence{1}.png'.format(path_outdir, str_suffix))

    # Count spectrum
    ax_stacked[0].loglog(x_stacked, model_sum_stacked, label='Sum of models')
    ax_stacked[0].loglog(x_stacked, model_grb_stacked, label='GRBs')
    ax_stacked[0].loglog(x_stacked, model_others_stacked, label='Others')
    ax_stacked[0].errorbar(x_stacked, nobs_sum_stacked, yerr=np.sqrt(nobs_sum_stacked), fmt='o',label='Counts')
    ax_stacked[0].legend(loc=1, fontsize=12)
    ax_stacked[0].set_ylabel('[counts]')
    ax_stacked[0].set_xticklabels([])
    ax_stacked[0].grid(ls='-', lw=0.5, alpha=0.2)
    #ax_stacked[0].set_xlabel(r'$\log_{10}Energy$ [MeV]')

    resid_stacked = (nobs_sum_stacked - model_sum_stacked) / model_sum_stacked
    resid_stacked_err = np.sqrt(nobs_sum_stacked) / model_sum_stacked
    ax_stacked[1].set_xscale('log')
    ax_stacked[1].errorbar(x_stacked, resid_stacked, yerr=resid_stacked_err, fmt='o')
    ax_stacked[1].axhline(0.0,ls=':')
    ax_stacked[1].grid(ls='-', lw=0.5, alpha=0.2)
    #ax_stacked].set_xlabel(r'$\log{10}Energy$ [MeV]')
    ax_stacked[1].set_xlabel(r'$\log_{10}Energy \rm{[MeV]}$')
    ax_stacked[1].set_ylabel('Fractional residual')

    fig_stacked.tight_layout()
    fig_stacked.subplots_adjust(hspace=0)
    ax_stacked[1].set_yticks([y for y in ax_stacked[1].get_yticks() if y<ax_stacked[1].get_ylim()[1]])

    nobs_denominator = np.zeros_like(nobs_sum_stacked)
    for (inobs_den, nobs_den) in enumerate(nobs_sum_stacked):
        nobs_denominator[inobs_den] = max(1, nobs_den)

    for ff in ('pdf', 'png'):
        fig_stacked.savefig('{0}/plots/StackedSpectrum{1}_category{2}.{3}'.format(path_outdir, str_suffix, ncat_analyzed, ff))


@click.command()
@click.argument('inputs', type=str)
@click.option('--pathout', '-o', type=str, default='.')
@click.option('--suffix', '-s', type=str, default='')
@click.option('--tieuniv', multiple=True, type=str)
@click.option('--tiecat', multiple=True, type=str)
@click.option('--category', type=click.Choice(['0', '1', '2', '3']), help='0: all GRBs 1,2,3: only GRBs of each category')
def main(inputs, pathout, category, tieuniv, tiecat, suffix):
    with open(inputs, "r") as filein:
        str_paths = filein.read()
        input_paths = str_paths.split('\n')[:-1]
        print input_paths
        run_composite2(input_paths, pathout, tieuniv, tiecat, int(category), suffix)


if __name__ == '__main__':
    main()
