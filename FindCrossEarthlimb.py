#!/usr/bin/env python

import sys
import numpy as np
import click
import datetime
from astropy.io import fits
from astropy.coordinates import SkyCoord  # High-level coordinates
from astropy.coordinates import ICRS, Galactic, FK4, FK5  # Low-level frames
from astropy.coordinates import Angle, Latitude, Longitude  # Angles
import astropy.units as u
from array import array
import math
from math import cos, sin, tan, acos, asin, atan, radians, degrees
from pMETandMJD import *
import commands


def get_good_intervals(pathFileScAll, ra, dec, tsegments, zcut, thcut=65., torigin=0):
    """Look over spacecraft files and returns start-time list and stop-time list of good intervals.
"""
    print pathFileScAll
    coordsTgt = SkyCoord(ra, dec, unit="deg")
    print coordsTgt

    cmd = "ls {0}".format(pathFileScAll)
    ret = commands.getoutput(cmd)
    aPathFileScAll = ret.split("\n")
    aFileToI = []
    for iFileSc in range(len(aPathFileScAll)):
        strPathFileSc = aPathFileScAll[iFileSc]
        aFileToI.append(aPathFileScAll[iFileSc])

    for tStart, tStop in zip(tsegments[0], tsegments[1]):
        metStart = tStart + torigin
        metStop = tStop + torigin
        validtimes = []    
    
        for fileToI in aFileToI:
            timeStart = datetime.datetime.now() # For progress bar
            hdulistSC = fits.open(fileToI)
            tbdataSC = hdulistSC[1].data
            aSTART, aSTOP = tbdataSC.field('START'), tbdataSC.field('STOP')
            aRA_ZENITH = tbdataSC.field('RA_ZENITH')
            aDEC_ZENITH = tbdataSC.field('DEC_ZENITH')
            aRA_SCZ, aRA_SCX = tbdataSC.field('RA_SCZ'), tbdataSC.field('RA_SCX')
            aDEC_SCZ, aDEC_SCX = tbdataSC.field('DEC_SCZ'), tbdataSC.field('DEC_SCX')
            aLIVETIME = tbdataSC.field('LIVETIME')
            aDATA_QUAL = tbdataSC.field('DATA_QUAL')
            aLAT_CONFIG = tbdataSC.field('LAT_CONFIG')

            nTI = len(aSTART)
            print "  ", fileToI, "(", nTI, "intervals )"
            gstarts = []
            gstops = []
            glivetimes = []
            stop_prev = 0
            iTIR = 0
            for iTI in range(nTI):
                if aSTART[iTI]<stop_prev:
                    print 'Odd order!!!'
                    return 1
                if not aDATA_QUAL[iTI]>0:
                    print 'Bad time interval', aSTART[iTI], '-', aSTOP[iTI], ':', aDATA_QUAL[iTI]
                    continue
                if not aLAT_CONFIG[iTI]==1:
                    print 'LAT config:', aSTART[iTI], '-', aSTOP[iTI], ':', aLAT_CONFIG[iTI]
                    continue
                if aSTOP[iTI]<metStart or aSTART[iTI]>metStop:
                    continue
                else:
                    coordsSCZ = SkyCoord(aRA_SCZ[iTI], aDEC_SCZ[iTI], unit="deg")
                    coordsZenith = SkyCoord(aRA_ZENITH[iTI], aDEC_ZENITH[iTI], unit="deg")
                    angSCZ = coordsSCZ.separation(coordsTgt)
                    degSCZ = float(angSCZ.to_string(unit=u.deg, decimal=True))
                    angZenith = coordsZenith.separation(coordsTgt)
                    degZenith = float(angZenith.to_string(unit=u.deg, decimal=True))
                    if degZenith<zcut and degSCZ<thcut:
                        if aSTART[iTI]>=metStart and aSTOP[iTI]<=metStop:
                            tstart_rel = aSTART[iTI]-torigin
                            tstop_rel = aSTOP[iTI]-torigin
                            tti = aLIVETIME[iTI]
                        elif aSTART[iTI]<=metStart and aSTOP[iTI]>=metStop:
                            tstart_rel = metStart-torigin
                            tstop_rel = metStop-torigin
                            tti = metStop-metStart
                        elif aSTART[iTI]<metStart:
                            tstart_rel = metStart-torigin
                            tstop_rel = aSTOP[iTI]-torigin
                            tti = (tstop_rel-tstart_rel)/(aSTOP[iTI]-aSTART[iTI])*aLIVETIME[iTI]
                        elif aSTOP[iTI]>metStop:
                            tstart_rel = aSTART[iTI]-torigin
                            tstop_rel = metStop-torigin
                            tti = (tstop_rel-tstart_rel)/(aSTOP[iTI]-aSTART[iTI])*aLIVETIME[iTI]

                        if len(gstops)==0:
                            gstarts.append(tstart_rel)
                            gstops.append(tstop_rel)
                            glivetimes.append(tti)
                        else:
                            if tstart_rel==gstops[-1]:
                                gstops[-1] = tstop_rel
                                glivetimes[-1] += tti
                            else:
                                gstarts.append(tstart_rel)
                                gstops.append(tstop_rel)
                                glivetimes.append(tti)

                    if iTI%300==0:
                        print iTI, 'Time:', aSTART[iTI]-torigin, 'RA:', aRA_SCZ[iTI], 'DEC:', aDEC_SCZ[iTI], 'Zenith:', degZenith, 'Inclination:', degSCZ, 'LAT_MODE:', tbdataSC.field('LAT_MODE')[iTI]
                    sys.stdout.flush()
            if not len(gstarts)==len(gstops):
                print 'Numbers of START and STOP are NOT same!!!'
                sys.exit(1)
            if not len(gstarts)==len(glivetimes):
                print 'Numbers of START and LIVETIME are NOT same!!!'
                sys.exit(1)
        validtimes.append[(gstarts, gstops, glivetimes)]
    return validtimes

def find_cross_earthlimb(pathFileScAll, ra, dec, tStart, tStop, zcut, thcut=65., torigin=0):
    """Look over spacecraft files and find times the target object crosses the Earthlimb.
"""
    print pathFileScAll
    coordsTgt = SkyCoord(ra, dec, unit="deg")
    print coordsTgt
    metStart = tStart + torigin
    metStop = tStop + torigin
    fmwStart = ConvertMetToFMW(metStart)
    fmwStop = ConvertMetToFMW(metStop)
    validtimes = []
    
    print "Fermi Mission Week:", fmwStart, "-", fmwStop

    cmd = "ls {0}".format(pathFileScAll)
    ret = commands.getoutput(cmd)
    aPathFileScAll = ret.split("\n")
    aFileToI = []
    for iFileSc in range(len(aPathFileScAll)):
        strPathFileSc = aPathFileScAll[iFileSc]
        aFileToI.append(aPathFileScAll[iFileSc])
    timeStart = datetime.datetime.now() # For progress bar
    for fileToI in aFileToI:
        hdulistSC = fits.open(fileToI)
        tbdataSC = hdulistSC[1].data
        #tbdataSC.sort('START')
        aSTART, aSTOP = tbdataSC.field('START'), tbdataSC.field('STOP')
        aRA_ZENITH = tbdataSC.field('RA_ZENITH')
        aDEC_ZENITH = tbdataSC.field('DEC_ZENITH')
        aRA_SCZ = tbdataSC.field('RA_SCZ')
        aRA_SCX = tbdataSC.field('RA_SCX')
        aDEC_SCZ = tbdataSC.field('DEC_SCZ')
        aDEC_SCX = tbdataSC.field('DEC_SCX')
        aLIVETIME = tbdataSC.field('LIVETIME')
        aDATA_QUAL = tbdataSC.field('DATA_QUAL')
        aLAT_CONFIG = tbdataSC.field('LAT_CONFIG')
        degZenith_prev = 0
        degSCZ_prev = 0
        start_prev = 0
        stop_prev = 0
        nTI = len(aSTART)
        print "  ", fileToI, "(", nTI, "intervals )"
        iTIR = 0
        for iTI in range(nTI):
            if aSTART[iTI]<stop_prev:
                print 'Odd order!!!'
                return 1
            if not aDATA_QUAL[iTI]>0:
                print 'Bad time interval', aSTART[iTI], '-', aSTOP[iTI], ':', aDATA_QUAL[iTI]
                continue
            if not aLAT_CONFIG[iTI]==1:
                print 'LAT config:', aSTART[iTI], '-', aSTOP[iTI], ':', aLAT_CONFIG[iTI]
                continue
            if aSTOP[iTI]>=metStart and aSTART[iTI]<metStop:
                tti = aLIVETIME[iTI]
                coordsSCZ = SkyCoord(aRA_SCZ[iTI], aDEC_SCZ[iTI], unit="deg")
                coordsZenith = SkyCoord(aRA_ZENITH[iTI], aDEC_ZENITH[iTI], unit="deg")
                angSCZ = coordsSCZ.separation(coordsTgt)
                degSCZ = float(angSCZ.to_string(unit=u.deg, decimal=True))
                angZenith = coordsZenith.separation(coordsTgt)
                degZenith = float(angZenith.to_string(unit=u.deg, decimal=True))
                if iTIR==0:
                    if degZenith>=zcut:
                        print 'Your target is wihin Earthlimb (Z>{2}deg). ({0},{1})'.format(aSTART[iTI]-torigin, degZenith, zcut)
                    elif degSCZ>=thcut:
                        print 'Your target is outdside of the FoV (theta>{2}deg). ({0},{1})'.format(aSTART[iTI]-torigin, degSCZ, thcut)
                    else:
                        validtimes.append([max(metStart, aSTART[iTI])-torigin])
                elif degZenith>=zcut and degZenith_prev<zcut: # entering Earthlimb
                    print 'Your target is entring Earthlimb (Z>{4}deg). ({0},{1})->({2},{3})'.format(start_prev-torigin, degZenith_prev, aSTART[iTI]-torigin, degZenith, zcut)
                    if len(validtimes)>0 and len(validtimes[-1])<2: #degSCZ<thcut:
                        if stop_prev==aSTART[iTI]:
                            tcross = aSTART[iTI] + (aSTART[iTI]-start_prev)/(degZenith-degZenith_prev)*(zcut-degZenith)
                        else:
                            tcross = start_prev
                        print 'Crossing time:', tcross
                        validtimes[-1].append(tcross-torigin)
                    else:
                        print 'Your target is still outside of FoV (theta>={4}deg). ({0},{1})->({2},{3})'.format(start_prev-torigin, degSCZ_prev, aSTART[iTI]-torigin, degSCZ, thcut)
                elif degSCZ>=thcut and degSCZ_prev<thcut: # exiting FoV
                    print 'Your target is exiting FoV (theta>{4}deg). ({0},{1})->({2},{3})'.format(start_prev, degSCZ_prev, aSTART[iTI]-torigin, degSCZ, thcut)
                    if len(validtimes)>0 and len(validtimes[-1])<2: #degZenith_prev<zcut:
                        if stop_prev==aSTART[iTI]:
                            tcross = aSTART[iTI] + (aSTART[iTI]-start_prev)/(degSCZ-degSCZ_prev)*(thcut-degSCZ)
                        else:
                            tcross = start_prev
                        print 'Crossing time:', tcross
                        validtimes[-1].append(tcross-torigin)
                    else:
                        print 'Your target is still within Earthlimb (Z>{4}deg). ({0},{1})->({2},{3})'.format(start_prev-torigin, degZenith_prev, aSTART[iTI]-torigin, degZenith, zcut)
                elif degZenith<zcut and degZenith_prev>=zcut: # exiting Earthlimb
                    print 'Your target is exiting Earthlimb (Z>{4}deg). ({0},{1})->({2},{3})'.format(start_prev, degZenith_prev, aSTART[iTI]-torigin, degZenith, zcut)
                    if len(validtimes)==0 or len(validtimes[-1])==2: #degSCZ<thcut:
                        if stop_prev==aSTART[iTI]:
                            tcross = aSTART[iTI] + (aSTART[iTI]-start_prev)/(degZenith-degZenith_prev)*(zcut-degZenith)
                        else:
                            tcross = aSTART[iTI]
                        print 'Crossing time:', tcross
                        validtimes.append([aSTART[iTI]-torigin])
                    else:
                        print 'Your target is still outside of FoV (theta>={4}deg). ({0},{1})->({2},{3})'.format(start_prev-torigin, degSCZ_prev, aSTART[iTI]-torigin, degSCZ, thcut)
                elif degSCZ<thcut and degSCZ_prev>=thcut: # entering FoV
                    print 'Your target is entering FoV (theta<{4}deg). ({0},{1})->({2},{3})'.format(start_prev, degSCZ_prev, aSTART[iTI]-torigin, degSCZ, thcut)
                    if len(validtimes)==0 or len(validtimes[-1])==2: #degZenith<zcut:
                        if stop_prev==aSTART[iTI]:
                            tcross = aSTART[iTI] + (aSTART[iTI]-start_prev)/(degZenith-degZenith_prev)*(zcut-degZenith)
                        else:
                            tcross = aSTART[iTI]
                        print 'Crossing time:', tcross
                        validtimes.append([aSTART[iTI]-torigin])
                    else:
                        print 'Your target is still within Earthlimb (Z>{4}deg). ({0},{1})->({2},{3})'.format(start_prev-torigin, degZenith_prev, aSTART[iTI]-torigin, degZenith, zcut)
                elif degSCZ<thcut and degZenith<zcut and aSTART[iTI]-stop_prev>1:
                    print 'Gap in observation from {0} - {1}'.format(stop_prev-torigin, aSTART[iTI]-torigin)
                    validtimes[-1].append(stop_prev-torigin)
                    validtimes.append([aSTART[iTI]-torigin])
                degZenith_prev = degZenith
                degSCZ_prev = degSCZ
                start_prev = aSTART[iTI]
                stop_prev = aSTOP[iTI]
                iTIR +=1

                if iTI%300==0:
                    print iTI, 'Time:', aSTART[iTI]-torigin, 'RA:', aRA_SCZ[iTI], 'DEC:', aDEC_SCZ[iTI], 'Zenith:', degZenith, 'Inclination:', degSCZ, 'LAT_MODE:', tbdataSC.field('LAT_MODE')[iTI]#math.degrees(aAngSCY[1]), math.degrees(math.pi/2.-aAngSCY[0]), degZenith, math.degrees(radSCY)
                sys.stdout.flush()
        if len(validtimes[-1])<2:
            validtimes[-1].append(min(metStop, aSTART[nTI-1])-torigin)
        return validtimes


@click.command()
@click.argument('scfiles', type=str)
@click.argument('ra', type=float)
@click.argument('dec', type=float)
@click.option('--zcut', type=float, default=100.)
@click.option('--torigin', type=float, default=0.)
@click.option('--start', type=float, default=0)
@click.option('--stop', type=float, default=599529605) #2020-01-01
def main(scfiles, ra, dec, zcut, start, stop, torigin):
    gti = find_cross_earthlimb(scfiles, ra, dec, start, stop, zcut, torigin)
    print gti

if __name__ == '__main__':
    main()
