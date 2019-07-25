import pickle

import numpy as np
import matplotlib.pylab as plt
from  scipy.constants import physical_constants

from cpymad.madx import Madx

import pysixtrack
from pysixtrack.particles import Particles
import pysixtrack.be_beamfields.tools as bt

mass = physical_constants['proton mass energy equivalent in MeV'][0]*1e6
p0c = 25.92e9
intensity=2e11 
neps_x=2e-6
neps_y=2e-6
dpp_rms=1.5e-3
bunchlength_rms = 0.22
V_RF_MV = 4.5
lag_RF_deg = 180.
n_SCkicks = 100 #80
length_fuzzy = 1.5
seq_name = 'sps'

betagamma = p0c/mass

def determine_sc_locations(line, n_SCkicks, length_fuzzy):
    s_elements = np.array(line.get_s_elements())
    length_target = s_elements[-1] / float(n_SCkicks)
    s_targets = np.arange(0,s_elements[-1],length_target)
    sc_locations = []
    for s in s_targets:
        idx_closest = (np.abs(s_elements - s)).argmin()
        s_closest = s_elements[idx_closest]
        if abs(s-s_closest)<length_fuzzy/2.:
            sc_locations.append(s_closest)
        else:
            sc_locations.append(s)
    sc_lengths = np.diff(sc_locations).tolist() + [s_elements[-1]-sc_locations[-1]]
    return sc_locations, sc_lengths

def install_sc_placeholders(mad, seq_name, name, s, mode='Bunched'):
    mad.input('''
            seqedit, sequence=??SEQNAME??;'''.replace('??SEQNAME??',seq_name))
    for name_, s_ in zip(np.atleast_1d(name), np.atleast_1d(s)): 
        mad.input('''
            ??NAME?? : placeholder, l=0., slot_id=??SID??;
            install, element=??NAME??, at=??POS??;'''.replace(
                    '??NAME??', name_).replace('??POS??', '%.10e'%s_).replace(
                    '??SID??', {'Coasting':'1', 'Bunched':'2'}[mode]))
    mad.input('''
            flatten;
            endedit;
            use, sequence=??SEQNAME??;'''.replace('??SEQNAME??',seq_name))

    
mad = Madx()
mad.options.echo=False
mad.options.info=False
mad.warn=False 
mad.chdir('madx')
mad.call('sps_thin.madx')
mad.use(seq_name)

# Determine space charge locations
temp_line, other = pysixtrack.Line.from_madx_sequence(mad.sequence.sps)                             
sc_locations, sc_lengths = determine_sc_locations(temp_line, n_SCkicks, length_fuzzy)

# Install spacecharge place holders
sc_names = ['sc%d'%number for number in range(len(sc_locations))]
install_sc_placeholders(mad, seq_name, sc_names, sc_locations, mode='Bunched')

# twiss
twtable = mad.twiss()

# Get position and sigma and sc locations


# Generate line with spacecharge
line, other = pysixtrack.Line.from_madx_sequence(mad.sequence.sps)                             

# Setup spacecharge
_, mad_sc_names, points, twdata = bt.get_points_sigmas_for_element_type(
        mad, seq_name, ele_type='placeholder', slot_id=2,
        use_survey=False, use_twiss=True)

sc_elements, sc_names = line.get_elements_of_type(pysixtrack.elements.SpaceChargeBunched)

assert(len(sc_elements)==len(mad_sc_names))
assert(len(sc_lengths)==len(mad_sc_names))
for ii, (ss, nn) in enumerate(zip(sc_elements, sc_names)):
    assert(nn == mad_sc_names[ii])
    
    ss.number_of_particles = intensity
    ss.bunchlength_rms = bunchlength_rms
    ss.sigma_x = np.sqrt(twdata['betx'][ii]*neps_x/betagamma + (
        twdata['dispersion_x'][ii]*dpp_rms)**2)
    ss.sigma_y = np.sqrt(twdata['bety'][ii]*neps_y/betagamma + (
        twdata['dispersion_y'][ii]*dpp_rms)**2)
    ss.length = sc_lengths[ii]
    ss.Delta_x = twdata['x'][ii]
    ss.Delta_y = twdata['y'][ii]
    ss.enabled=True

# enable RF
i_cavity = line.element_names.index('acta.31637')
line.elements[i_cavity].voltage = V_RF_MV * 1e6
line.elements[i_cavity].lag = lag_RF_deg


with open('line.pkl', 'wb') as fid:
    pickle.dump(line.to_dict(keepextra=True), fid)


''

import matplotlib.patches as patches
if 0:
    plt.close('all')

    f, ax = plt.subplots()
    ax.hist(sc_lengths, bins=np.linspace(0,max(sc_lengths)+0.1,100))
    ax.set_xlabel('length of SC kick (m)')
    ax.set_ylabel('counts')
    ax.set_xlim(left=0)
    plt.show()

    f, ax = plt.subplots(figsize=(14,5))
    ax.plot(twtable.s, twtable.betx, 'b', label='x', lw=2)
    ax.plot(twtable.s, twtable.bety, 'g', label='x', lw=2)
    for s in sc_locations: ax.axvline(s, linewidth=1, color='r', linestyle='--')
    ax.set_xlim(0,1100)
    ax.set_ylim(0,120)
    ax.set_xlabel('s (m)')
    ax.set_ylabel('beta functions (m)')
    ax.legend(loc=3)
    plt.show()


''
