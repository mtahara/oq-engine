# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2014, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.


"""
Reading risk models for risk calculators
"""

import collections
from openquake.risklib import scientific, workflows
from openquake.nrmllib.risk import parsers


def get_vulnerability_functions(vulnerability_file):
    """
    :param vulnerability_file:
        the pathname to a vulnerability file
    :returns:
        a dictionary {taxonomy: (imt, vulnerability_function)}
    :raises:
        * `ValueError` if validation of any vulnerability function fails
    """
    vfs = {}
    for record in parsers.VulnerabilityModelParser(vulnerability_file):
        taxonomy = record['ID']
        imt = record['IMT']
        loss_ratios = record['lossRatio']
        covs = record['coefficientsVariation']
        distribution = record['probabilisticDistribution']

        if taxonomy in vfs:
            raise ValueError("Error creating vulnerability function for "
                             "taxonomy %s. A taxonomy can not "
                             "be associated with "
                             "different vulnerability functions" % taxonomy)
        try:
            vfs[taxonomy] = scientific.VulnerabilityFunction(
                imt, record['IML'], loss_ratios, covs, distribution)
        except ValueError, err:
            msg = "Invalid vulnerability function with ID '%s': %s" % (
                taxonomy, err.message)
            raise ValueError(msg)

    return vfs


class List(list):
    """
    Class to store lists of objects with common attributes
    """
    def __init__(self, elements, **attrs):
        list.__init__(self, elements)
        vars(self).update(attrs)


def get_damage_states_and_risk_models(content):
    """
    Parse the fragility XML file and return a list of
    damage_states and a dictionary {taxonomy: risk model}
    """
    iterparse = iter(parsers.FragilityModelParser(content))
    fmt, limit_states = iterparse.next()

    damage_states = ['no_damage'] + limit_states
    fragility_functions = collections.defaultdict(dict)

    tax_imt = dict()
    for taxonomy, iml, params, no_damage_limit in iterparse:
        tax_imt[taxonomy] = iml['IMT']

        if fmt == "discrete":
            if no_damage_limit is None:
                fragility_functions[taxonomy] = [
                    scientific.FragilityFunctionDiscrete(
                        iml['imls'], poes, iml['imls'][0])
                    for poes in params]
            else:
                fragility_functions[taxonomy] = [
                    scientific.FragilityFunctionDiscrete(
                        [no_damage_limit] + iml['imls'], [0.0] + poes,
                        no_damage_limit)
                    for poes in params]
        else:
            fragility_functions[taxonomy] = [
                scientific.FragilityFunctionContinuous(*mean_stddev)
                for mean_stddev in params]

    risk_models = {}
    for taxonomy, ffs in fragility_functions.items():
        dic = dict(damage=List(ffs, imt=tax_imt[taxonomy]))
        risk_models[taxonomy] = workflows.RiskModel(
            taxonomy, workflows.Damage(dic))

    return damage_states, risk_models
