#!/usr/bin/python
# coding: utf-8
from __future__ import print_function
import pymongo as pm
import numpy as np
import argparse
from sys import argv
from os import makedirs
from os.path import exists, isfile
import bson.json_util as json
import re

class DBQuery:
    ''' Class that implements queries to MongoDB
    structure database.
    '''

    def __init__(self, **kwargs):
        ''' Initialise the query with command line
        arguments.
        '''
        self.client = pm.MongoClient()
        self.db = self.client.crystals
        self.repo = self.client.crystals.repo
        self.args = kwargs
        for arg in self.args:
            if type(self.args[arg]) == str:
                self.args[arg] = self.args[arg].split() 
        self.top = self.args.get('top') if self.args.get('top') != None else 10
        self.details = self.args.get('details')
        self.source = self.args.get('source')
        self.partial = self.args.get('partial_formula')
        self.summary = self.args.get('summary')
        self.tags = self.args.get('tags')
        self.cell = self.args.get('cell')
        self.res = self.args.get('res')
        # grab all args as string for file dumps
        if self.args.get('sysargs'):
            self.sysargs = ''.join((str(a)+'_' for a in self.args.get('sysargs')))
            self.sysargs = self.sysargs.replace('-','')
            self.sysargs = 'query-' + self.sysargs
        # benchmark enthalpy to display (set by calc_match)
        self.gs_enthalpy = 0.0
        if self.args.get('dbstats'):
            self.dbstats()
        if self.args.get('pressure') != None:
            cursor = self.repo.find(
                    {
                    'external_pressure': {'$in': [[self.args.get('pressure')]]}
                    }
                    )
            self.repo = self.temp_collection(cursor)
        if self.args.get('id') != None:
            cursor = self.repo.find({'text_id': self.args.get('id')})
            self.display_results(cursor, details=True)
            cursor = self.repo.find({'text_id': self.args.get('id')})
            if self.args.get('calc_match'):
                cursor = self.query_calc(cursor)
                if self.args.get('composition') != None or self.args.get('stoichiometry') != None:
                    self.repo = self.temp_collection(cursor)
        if self.args.get('stoichiometry') != None:
            cursor = self.query_stoichiometry()
        elif self.args.get('composition') != None:
            cursor = self.query_composition()
        elif self.args.get('tags') != None:
            cursor = self.query_tags()
        elif self.args.get('id') == None and self.args.get('dbstats') == False:
            cursor = self.repo.find().sort('enthalpy_per_atom', pm.ASCENDING)
        else:
            try:
                if cursor.count() <= 0:
                    cursor = EmptyCursor()
            except:
                cursor = EmptyCursor()
        # clone cursor for further use after printing
        self.cursor = cursor.clone()
        # write query to res or cell with param files
        if self.cell or self.res:
            if cursor.count() > 1:
                if self.args.get('top') != None:
                    self.query2files(self.cursor[:self.top], self.res, self.cell, top=True)
                else:
                    self.query2files(self.cursor, self.res, self.cell)
        # if called as script, always print results
        if self.args.get('main'):
            if cursor.count() > 1:
                if self.summary:
                    self.display_results(cursor, details=self.details)
                elif cursor.count() > self.top:
                    self.display_results(cursor[:self.top], details=self.details)
                else:
                    self.display_results(cursor, details=self.details)

    def __del__(self):
        ''' Clean up any temporary databases on garbage 
        collection of DBQuery object.
        '''
        try:
            self.temp.drop()
        except:
            pass

    def swaps(self, doc, counter, **kwargs):
        ''' Take a db document as input and perform atomic swaps. '''
        pairs = kwargs.get('pairs')
        swap_doc = doc.copy()
        swap_atoms = doc['atom_types'].copy()
        for swap_no in range(pairs):
            valid = False
            while not valid:    
                swap = np.random.randint(0, len(swap_atoms)-1, size=2)
                if swap[0] != swap[1] and swap_atoms[swap[0]] != swap_atoms[swap[1]]:
                        valid = True
            swap_atoms[swap[1]], swap_atoms[swap[0]] = swap_atoms[swap[0]], swap_atoms[swap[1]]
        self.doc2cell(swap_doc, str(counter), doc['text_id'][0]+doc['text_id'][1]+'swaps')


    def query2files(self, cursor, res=False, cell=False, top=False):
        ''' Write .res or .cell files for all docs in query,
        including a .param file for each. Eventually handle
        swaps from one element to another from CLI.
        '''
        if cursor.count() > 1000 and top == False:
            write = raw_input('This operation will write ' + str(cursor.count()) + ' structures,' \
                    + ' are you sure you want to do this? [y/n] ')
            if write == 'y' or write == 'Y':
                print('Writing them all.')
                write = True
            else:
                write = False
                return
        else:
            print('Writing the top', self.top, 'of them.')
            write = True
        name = self.sysargs
        dir = False
        dir_counter = 0
        while not dir:
            if dir_counter != 0:
                directory = name + str(dir_counter)
            else:
                directory = name
            if not exists(directory):
                makedirs(directory)
                dir = True
            else:
                dir_counter += 1
        for ind, doc in enumerate(cursor):
            path = directory + '/'
            # write either cell, res or both
            for source in doc['source']:
                if '.res' in source:
                    name = source.split('/')[-1].split('.')[0]
                elif '.castep' in source:
                    name = source.split('/')[-1].split('.')[0]
                elif '.history' in source:
                    name = source.split('/')[-1].split('.')[0]
            path += name
            if cell:
                self.doc2cell(doc, str(ind), path)
            if res:
                self.doc2res(doc, str(ind), path)
            # always write param for each doc
            self.doc2param(doc, str(ind), path)

    def doc2param(self, doc, counter, path):
        ''' Write basic .param file from single doc. '''
        param_list = ['task', 'cut_off_energy', 'norman', 'xc_functional',
                'finite_basis_corr', 'spin_polarized']
        try:
            if isfile(path+'.param'):
                path += '-' + str(counter)
            with open(path+'.param', 'w') as f:
                f.write('# Param file generated by fryan.py (Matthew Evans 2016)\n\n')
                for param in [param for param in param_list if param in doc]:
                    f.write("{0:20}: {1}\n".format(param, doc[param]))
        except Exception as oops:
            print('Writing param file failed for ', doc['text_id'])
            print(oops)

    def doc2cell(self, doc, counter, path):
        ''' Write .cell file for single doc. '''
        try:
            if isfile(path+'.cell'):
                path += '-' + str(counter)
            with open(path+'.cell', 'w') as f:
                f.write('# Cell file generated by fryan.py (Matthew Evans 2016)\n\n')
                f.write('%BLOCK LATTICE_ABC\n')
                for vec in doc['lattice_abc']:
                    for coeff in vec:
                        f.write(str(coeff) + ' ')
                    f.write('\n')
                f.write('%ENDBLOCK LATTICE_ABC\n\n')
                f.write('%BLOCK POSITIONS_FRAC\n')
                for ind, atom in enumerate(zip(doc['atom_types'], doc['positions_frac'])):
                    f.write("{0:8s} {1[0]: 15f} {1[1]: 15f} {1[2]: 15f}   1.0\n".format(atom[0], \
                            atom[1]))
                f.write('%ENDBLOCK POSITIONS_FRAC\n\n')
                try:
                    f.write('kpoints_mp_spacing : ' + str(doc['kpoints_mp_spacing']) + '\n')
                except:
                    pass
                f.write('\n%BLOCK SPECIES_POT\n')
                for elem in doc['species_pot']:
                    f.write(elem + '\t' + doc['species_pot'][elem] + '\n')
                f.write('%ENDBLOCK SPECIES_POT')
        except Exception as oops:
            print('Writing cell file failed for ', doc['text_id'])
            print(oops)

    def doc2res(self, doc, counter, path):
        ''' Write .res file for single doc. '''
        try:
            if isfile(path+'.res'):
                path += '-' + str(counter)
            with open(path+'.res', 'w') as f:
                f.write('# Res file generated by fryan.py (Matthew Evans 2016)\n\n')
                f.write('TITL ')
                f.write(path.split('/')[-1] + counter + ' ')
                f.write(str(doc['pressure']) + ' ')
                f.write(str(doc['cell_volume']) + ' ')
                f.write(str(doc['enthalpy']) + ' ')
                f.write('0 0 ')             # spin
                f.write(str(doc['num_atoms']) + ' ')
                try:
                    f.write('(' + str(doc['space_group']) + ')' + ' ')
                except:
                    f.write('xxx ')
                f.write('n - 1')
                f.write('\n')
                f.write('CELL ')
                f.write('1.0 ')
                for vec in doc['lattice_abc']:
                    for coeff in vec:
                        f.write(str(coeff) + ' ')
                f.write('\n')
                f.write('LATT -1\n')
                f.write('SFAC \t')
                for elem in doc['stoichiometry']:
                    f.write(str(elem[0]) + ' ')
                f.write('\n')
                atom_labels = []
                i = 0
                j = 1
                while i < len(doc['atom_types']):
                    num = doc['atom_types'].count(doc['atom_types'][i])
                    atom_labels.extend(num*[j])
                    i += num
                    j += 1
                for ind, atom in enumerate(zip(doc['atom_types'], atom_labels, doc['positions_frac'])):
                    f.write("{0:8s}{1:3d}{2[0]: 15f} {2[1]: 15f} {2[2]: 15f}   1.0\n".format(atom[0], \
                            atom[1], atom[2]))
                f.write('END')
        except Exception as oops:
            print('Writing cell file failed for ', doc['text_id'])
            print(oops)

    def display_results(self, cursor, details=False):
        ''' Print query results in a cryan-like fashion. '''
        struct_string = []
        detail_string = []
        detail_substring = []
        source_string = []
        summary_string = []
        formula_string = []
        last_formula = ''
        gs_enthalpy = 0
        header_string = "{:^24}".format('ID')
        header_string += "{:^12}".format('Pressure')
        header_string += "{:^12}".format('Volume/fu') 
        header_string += "{:^18}".format('Enthalpy/atom')
        header_string += "{:^12}".format('Space group')
        header_string += "{:^10}".format('Formula')
        header_string += "{:^8}".format('# fu')
        for ind, doc in enumerate(cursor):
            formula_substring = ''
            if 'phase' in doc:
                if 'alpha' in doc['phase']:
                    formula_substring += 'α-'
                elif 'beta' in doc['phase']:
                    formula_substring += 'β-'
                elif 'gamma' in doc['phase']:
                    formula_substring += 'γ-'
                elif 'theta' in doc['phase']:
                    formula_substring += 'θ-'
            atom_per_fu = 0
            for item in doc['stoichiometry']:
                for item_ind, subitem in enumerate(item):
                    if item_ind == 0:
                        formula_substring += str(subitem)
                    if item_ind == 1:
                        if subitem != 1:
                            formula_substring += str(subitem)
                        atom_per_fu += subitem
            if last_formula != formula_substring:
                self.gs_enthalpy = 0.0
            formula_string.append(formula_substring)
            struct_string.append(
                    "{:^24}".format(doc['text_id'][0]+' '+doc['text_id'][1]))
            try:
                struct_string[-1] += "{:^ 12.3f}".format(doc['pressure'])
            except: 
                struct_string[-1] += "{:^12}".format(doc['pressure'])
            try:
                struct_string[-1] += "{:^12.3f}".format(atom_per_fu * doc['cell_volume'] / doc['num_atoms'])
            except:
                struct_string[-1] += "{:^12}".format('xxx')
            try:
                struct_string[-1] += "{:^18.5f}".format(doc['enthalpy_per_atom'] - self.gs_enthalpy)
            except:
                struct_string[-1] += "{:^18}".format('xxx')
            try:
                struct_string[-1] += "{:^12}".format(doc['space_group'])
            except:
                struct_string[-1] += "{:^12}".format('xxx')
            struct_string[-1] += "{:^10}".format(formula_substring)
            struct_string[-1] += "{:^8}".format(doc['num_atoms']/atom_per_fu)
            if last_formula != formula_substring:
                self.gs_enthalpy = doc['enthalpy_per_atom']
            last_formula = formula_substring
            if details:
                detail_string.append(11 * ' ' + u"├╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ ")
                if self.source:
                    detail_substring.append(11 * ' ' + u"├╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ ")
                else:
                    detail_substring.append(11 * ' ' + u"└╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ ")
                if 'spin_polarized' in doc:
                    if doc['spin_polarized']:
                        detail_string[-1] += 'S-'
                if 'sedc_scheme' in doc:
                    detail_string[-1] += doc['sedc_scheme'].upper()+'+'
                if 'xc_functional' in doc:
                    detail_string[-1] += doc['xc_functional']
                else:
                    detail_string[-1] += 'functional unknown for' + doc['source'][0]
                if 'cut_off_energy' in doc:
                    detail_string[-1] += ', ' + "{:4.2f}".format(doc['cut_off_energy']) + ' eV'
                else:
                    detail_string[-1] += 'cutoff unknown'
                if 'external_pressure' in doc:
                    detail_string[-1] += ', ' + "{:4.2f}".format(doc['external_pressure'][0][0]) + ' GPa'
                if 'kpoints_mp_spacing' in doc:
                    detail_string[-1] += ', ' + str(doc['kpoints_mp_spacing']) + ' 1/A'
                if 'species_pot' in doc:
                    try:
                        for species in doc['species_pot']:
                            detail_substring[-1] += doc['species_pot'][species] + ', '
                    except:
                        pass
                if 'icsd' in doc:
                    detail_substring[-1] += 'ICSD-CollCode' + doc['icsd'] + ', '
                if 'tags' in doc:
                    try:
                        for tag in doc['tags']:
                            detail_substring[-1] += tag + ', '
                    except:
                        pass
                if 'user' in doc:
                    detail_substring[-1] += doc['user']
                detail_string[-1] += ' ' + (len(header_string)-len(detail_string[-1])-1)*u"╌"
                detail_substring[-1] += ' ' + (len(header_string)-len(detail_substring[-1])-1)*u"╌"
            if self.source:
                source_string.append(11*' ' + u"└───────────────┬──")
                for num, file in enumerate(doc['source']):
                    if num == len(doc['source'])-1:
                        source_string[-1] += (len(u"└────────────── ")+11)*' ' + u'└──'
                    elif num != 0:
                        source_string[-1] += (len(u"└────────────── ")+11)*' ' + u'├──'
                    # elif num == 0:
                    source_string[-1] += ' ' + file[2:] 
                    if num != len(doc['source'])-1:
                        source_string[-1] += '\n'
        print(len(header_string)*'─')
        print(header_string)
        print(len(header_string)*'─')
        if self.summary:
            current_formula = ''
            count = 0
            for ind, string in enumerate(formula_string):
                if count > self.top:
                    break
                if string != current_formula and string not in formula_string[:ind]:
                    count += 1
                    print(struct_string[ind])
                    if details:
                        print(detail_string[ind])
                        print(detail_substring[ind])
                    if self.source:
                        print(source_string[ind])
                    current_formula = string
        else:
            for ind, string in enumerate(struct_string):
                print(string)
                if details:
                    print(detail_string[ind])
                    print(detail_substring[ind])
                if self.source:
                    print(source_string[ind])
                if details or self.source:
                    print(len(header_string)*'─')
        
    def query_stoichiometry(self):
        ''' Query DB for particular stoichiometry. '''
        # alias stoichiometry
        stoich = self.args.get('stoichiometry')
        # if there's only one string, try split it by caps
        if len(stoich) == 1:
            stoich = [elem for elem in re.split(r'([A-Z][a-z]*)', stoich[0]) if elem]
        elements = []
        fraction = []
        for i in range(0, len(stoich), 1):
            if not bool(re.search(r'\d', stoich[i])):
                elements.append(stoich[i])
                try:
                    fraction.append(float(stoich[i+1]))
                except:
                    fraction.append(1.0)
        fraction = np.asarray(fraction)
        fraction /= np.min(fraction)
        # pyMongo doesn't like generators... could patch pyMongo?
        # cursor = self.repo.find({'stoichiometry.'+[element for element in elements]: {'$exists' : True}})
        if self.partial:
            if len(elements) == 1:
                cursor = self.repo.find({'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}})
            elif len(elements) == 2:
                cursor = self.repo.find({ '$and': [ 
                                            {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}}
                                        ]})
            elif len(elements) == 3:
                cursor = self.repo.find({ '$and': [ 
                                            {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[2], fraction[2]]]}}
                                        ]})
            elif len(elements) == 4:
                cursor = self.repo.find({ '$and': [ 
                                            {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[2], fraction[2]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[3], fraction[3]]]}}
                                        ]})
        else:
            if len(elements) == 1:
                cursor = self.repo.find({'stoichiometry' : [[elements[0], fraction[0]]]})
            elif len(elements) == 2:
                cursor = self.repo.find({ '$and': [ 
                                            {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                            {'stoichiometry' : {'$size' : 2}}
                                        ]})
            elif len(elements) == 3:
                cursor = self.repo.find({ '$and': [ 
                                            {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[2], fraction[2]]]}},
                                            {'stoichiometry' : {'$size' : 3}}
                                        ]})
            elif len(elements) == 4:
                cursor = self.repo.find({ '$and': [ 
                                            {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[2], fraction[2]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[3], fraction[3]]]}},
                                            {'stoichiometry' : {'$size' : 4}}
                                        ]})
            elif len(elements) == 5:
                cursor = self.repo.find({ '$and': [ 
                                            {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[2], fraction[2]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[3], fraction[3]]]}},
                                            {'stoichiometry' : {'$in' : [[elements[4], fraction[4]]]}},
                                            {'stoichiometry' : {'$size' : 5}}
                                        ]})
        cursor.sort('enthalpy_per_atom', pm.ASCENDING)
        print(cursor.count(), 'structures found with the desired stoichiometry.')
        return cursor
    
    def query_composition(self):
        ''' Query DB for all structures containing 
        all the elements taken as input.
        '''
        elements = self.args.get('composition')
        # if there's only one string, try split it by caps
        numeracy = False
        if len(elements) == 1:
            elements = [elem for elem in re.split(r'([A-Z][a-z]*)', elements[0]) if elem]
            if elements[0].isdigit():
                numeracy = True
        try:
            if numeracy == False:
                for elem in elements:
                    if bool(re.search(r'\d', elem)):
                        raise RuntimeError('Composition string must be a list of elements of a single number.')
        except Exception as oops:
            print(oops)
            return EmptyCursor()
        # pyMongo doesn't like generators... could patch pyMongo?
        # cursor = self.repo.find({'stoichiometry.'+[element for element in elements]: {'$exists' : True}})
        if self.partial:
            try:
                if numeracy:
                    raise RuntimeError('Number of elements not compatible with partial formula.')
            except Exception as oops:
                print(oops)
                return EmptyCursor()
            if len(elements) == 1:
                cursor = self.repo.find({'atom_types' : {'$in' : [elements[0]]}})
            elif len(elements) == 2:
                cursor = self.repo.find({ '$and': [ 
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'atom_types' : {'$in' : [elements[1]]}}
                                        ]})
            elif len(elements) == 3:
                cursor = self.repo.find({ '$and': [ 
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'atom_types' : {'$in' : [elements[1]]}},
                                            {'atom_types' : {'$in' : [elements[2]]}}
                                        ]})
            elif len(elements) == 4:
                cursor = self.repo.find({ '$and': [ 
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'atom_types' : {'$in' : [elements[1]]}},
                                            {'atom_types' : {'$in' : [elements[2]]}},
                                            {'atom_types' : {'$in' : [elements[3]]}}
                                        ]})
        else:
            if numeracy == True:
                cursor = self.repo.find({'stoichiometry' : {'$size' : int(elements[0])}})
            elif len(elements) == 1:
                cursor = self.repo.find({ '$and': [
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'stoichiometry' : {'$size' : 1}}
                                        ]})
            elif len(elements) == 2:
                cursor = self.repo.find({ '$and': [ 
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'atom_types' : {'$in' : [elements[1]]}},
                                            {'stoichiometry' : {'$size' : 2}}
                                        ]})
            elif len(elements) == 3:
                cursor = self.repo.find({ '$and': [ 
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'atom_types' : {'$in' : [elements[1]]}},
                                            {'atom_types' : {'$in' : [elements[2]]}},
                                            {'stoichiometry' : {'$size' : 3}}
                                        ]})
            elif len(elements) == 4:
                cursor = self.repo.find({ '$and': [ 
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'atom_types' : {'$in' : [elements[1]]}},
                                            {'atom_types' : {'$in' : [elements[2]]}},
                                            {'atom_types' : {'$in' : [elements[3]]}},
                                            {'stoichiometry' : {'$size' : 4}}
                                        ]})
            elif len(elements) == 5:
                cursor = self.repo.find({ '$and': [ 
                                            {'atom_types' : {'$in' : [elements[0]]}},
                                            {'atom_types' : {'$in' : [elements[1]]}},
                                            {'atom_types' : {'$in' : [elements[2]]}},
                                            {'atom_types' : {'$in' : [elements[3]]}},
                                            {'atom_types' : {'$in' : [elements[4]]}},
                                            {'stoichiometry' : {'$size' : 5}}
                                        ]})
        cursor.sort('enthalpy_per_atom', pm.ASCENDING)
        print(cursor.count(), 'structures found with desired composition.')
        return cursor

    def query_calc(self, cursor):
        ''' Find all structures with matching
        accuracy to specified structure. '''
        doc = cursor[0]
        self.gs_enthalpy = doc['enthalpy_per_atom']
        if cursor.count() != 1:
            return cursor
        else:
            cursor_match = self.repo.find({ '$and': [
                                        {'xc_functional' : doc['xc_functional']},
                                        {'cut_off_energy': doc['cut_off_energy']},
                                        {'external_pressure': doc['external_pressure']}
                                    ]})
            cursor_match.sort('enthalpy_per_atom', pm.ASCENDING)
            print(cursor_match.count(), 'structures found with parameters above.')
            return cursor_match
    
    def query_tags(self):
        ''' Find all structures matching given tags. '''
        if len(self.tags) == 1:
            cursor = self.repo.find({'tags' : {'$in' : [self.tags[0]]}
                                    })
        elif len(self.tags) == 2:
            cursor = self.repo.find({ '$and': [
                                        {'tags' : {'$in' : self.tags[0]}},
                                        {'tags' : {'$in' : self.tags[1]}}
                                    ]})
        elif len(self.tags) == 3:
            cursor = self.repo.find({ '$and': [
                                        {'tags' : {'$in' : self.tags[0]}},
                                        {'tags' : {'$in' : self.tags[1]}},
                                        {'tags' : {'$in' : self.tags[2]}}
                                    ]})
        elif len(self.tags) > 3:
            print('Too many tags, no structures found.')
            return EmptyCursor()
        else:
            print('No structures found with tags', self.tags)
            return EmptyCursor()
        cursor.sort('enthalpy_per_atom', pm.ASCENDING)
        return cursor

    def dbstats(self):
        ''' Print some useful stats about the database. ''' 
        db_stats_dict = self.db.command('collstats', self.repo.name)
        print('Database collection', self.db.name + '.' + self.repo.name, 'contains', db_stats_dict['count'],
              'structures at', "{:.1f}".format(db_stats_dict['avgObjSize']/1024), 'kB each, totalling', 
              "{:.1f}".format(db_stats_dict['storageSize']/(1024**2)), 'MB when padding is included.')
        cursor = self.repo.find()
        comp_list = dict()
        for doc in cursor:
            temp = ''
            for ind, elem in enumerate(doc['stoichiometry']):
                temp += str(elem[0])
                if ind != len(doc['stoichiometry'])-1:
                    temp += '+'
            if temp not in comp_list:
                comp_list[temp] = 0
            comp_list[temp] += 1
        keys = list(comp_list.keys())
        vals = list(comp_list.values())
        comp_list = zip(keys, vals)
        comp_list.sort(key = lambda t:t[1], reverse=True)
        small_list = []
        small_count = 0
        first_ind = 1000
        cutoff = 200
        for ind, comp in enumerate(comp_list):
            if comp[1] < cutoff:
                if ind < first_ind:
                    first_ind = ind
                small_list.append(comp[0])
                small_count += comp[1]
        comp_list = comp_list[:first_ind] 
        comp_list.append(['others < ' + str(cutoff), small_count])
        comp_list.sort(key = lambda t:t[1], reverse=True)
        from ascii_graph import Pyasciigraph
        from ascii_graph.colors import Gre, Blu, Yel, Red
        from ascii_graph.colordata import hcolor
        graph = Pyasciigraph(line_length=80, multivalue=False)
        db_stats_dict['count']
        thresholds = {int(db_stats_dict['count']/40): Gre, int(db_stats_dict['count']/10): Blu, int(db_stats_dict['count']/4): Red,}
        data = hcolor(comp_list, thresholds)
        for line in graph.graph(label=None, data=data):
           print(line) 
        print('where others', end=': ')
        for small in small_list:
            print(small, end=', ')
        print('\n')

    def temp_collection(self, cursor):
        ''' Create temporary collection
        for successive filtering. 
        '''
        # check temp doesn't already exist; drop if it does
        try:
            self.client.crystals.temp.drop()
        except:
            pass
        self.temp = self.client.crystals.temp
        if cursor.count() != 0:
            self.temp.insert(cursor)
        else:
            self.temp.drop()
            exit('No structures found.')
        return self.temp

class EmptyCursor:
    ''' Empty cursor class for failures. '''
    def count(self):
        return 0 
    def clone(self):
        return EmptyCursor()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Query MongoDB structure database.',
            epilog='Written by Matthew Evans (2016). Based on the cryan concept by Chris Pickard.')
    group = parser.add_argument_group()
    group.add_argument('-f', '--formula', nargs='+', type=str,
        help='choose a stoichiometry, e.g. Ge 1 Te 1 Si 3, or GeTeSi3')
    group.add_argument('-c', '--composition', nargs='+', type=str,
        help=('find all structures containing the given elements, e.g. GeTeSi, or find' +
        'the number of structures with n elements, e.g. 1, 2, 3'))
    parser.add_argument('-s', '--summary', action='store_true',
            help='show only the ground state for each formula (i.e. phase+stoichiometry)')
    group.add_argument('-i', '--id', type=str, nargs='+',
            help='specify a particular structure by its text_id')
    parser.add_argument('-t', '--top', type=int,
            help='number of structures to show (DEFAULT: 10)')
    parser.add_argument('-d', '--details', action='store_true',
            help='show as much detail about calculation as possible')
    parser.add_argument('-p', '--pressure', type=float,
            help='specify an isotropic external pressure to search for, e.g. 10 (GPa)')
    parser.add_argument('--source', action='store_true',
            help='print filenames from which structures were wrangled')
    parser.add_argument('-ac', '--calc-match', action='store_true',
            help='display calculations of the same accuracy as specified id')
    parser.add_argument('-pf', '--partial-formula', action='store_true',
            help=('stoichiometry/composition queries will include other unspecified species,' +
            'e.g. search for Ge2Te3 will also return Ge2Te3Si or Ge4Te6Fe2, and search for Li will' +
            ' include any structure containing Li, not just pure Li.'))
    parser.add_argument('--dbstats', action='store_true',
            help=('print some stats about the database that is being queried'))
    parser.add_argument('--tags', nargs='+', type=str,
            help=('search for up to 3 manual tags at once'))
    parser.add_argument('--cell', action='store_true',
            help='export query to .cell files in folder name from query string')
    parser.add_argument('--res', action='store_true',
            help='export query to .res files in folder name from query string')
    args = parser.parse_args()
    if args.calc_match and args.id == None:
        exit('--calc-match requires -i or --id')
    query = DBQuery(stoichiometry=args.formula, composition=args.composition,
                    summary=args.summary, id=args.id, top=args.top, details=args.details,
                    pressure=args.pressure, source=args.source, calc_match=args.calc_match,
                    partial_formula=args.partial_formula, dbstats=args.dbstats,
                    tags=args.tags, res=args.res, cell=args.cell, main=True, sysargs=argv[1:])
