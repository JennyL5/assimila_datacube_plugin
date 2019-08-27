# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AssimilaDatacCube
                                 A QGIS plugin
 This plugin let's you visualise the datacube.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-08-07
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Assimila
        email                : jenny.lin@assimila.eu
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import QgsProject, Qgis
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox
from qgis.utils import plugins, reloadPlugin, loadPlugin, startPlugin, isPluginLoaded

import numpy as np

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .assimila_datacube_dialog import AssimilaDatacCubeDialog
import os.path
from os.path import expanduser
import tempfile

# Import DQTools to set up connection to database
from .DQTools.DQTools import Search, Dataset 


class AssimilaDatacCube:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """

        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'AssimilaDatacCube_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Assimila Data Cube')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.dlg = AssimilaDatacCubeDialog(iface)


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('AssimilaDatacCube', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/assimila_datacube/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Visualise the datacube.'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Assimila Data Cube'),
                action)
            self.iface.removeToolBarIcon(action)

    def check(self, north, east, south, west, start, end):
        """
        Performs checks: start date is before end date, restricting frequency,
        east value is larger than west, and north value is larger than south.
        :param north: The name of the north point
        :param east: The name of the east point
        :param south: The name of the south point
        :param west: The name of the west point
        :param start: The start date
        :param end: The end date
        :return:
        """

        # check start is after end date
        if str(end)<str(start):
            raise ValueError('End date should not be before start date')
        
        # check that end date does not exceed 30 days from start date
            # limit is 30 days 23 hours
            # 01/01/2000 - 31/01/2000 -> SUCCESS 
            # 01/01/2000 - 01/02/2000 -> FAIL 
        if start.daysTo(end) > 30:
            raise ValueError('Maximum number of delays selected is limited to 30 days')

        # check east value is greater than west value
        if east != 0 and west != 0 and east < west:
            raise ValueError('East value should be greater than west')

        # check north value is greater than south value
        if north != 0 and south != 0 and north < south:
            raise ValueError('North value should be greater than south')
        
        # check area of box is less than 25*25=625
        print ('N-S=' + str(north - south))
        print ('E-W=' + str(east - west))
        print ('Total area = ' + str((north - south) * (east - west))) 
        if (north - south) * (east - west) > 625:
            raise ValueError('Exceeded maximum area of canvas')

    def subproduct_selectionchange(self):
        """
        Updates the subproduct combo box to give a list of subproducts
        of the selected product.
        :return:
        """
        self.dlg.subproducts_comboBox.clear()
        product = self.dlg.products_comboBox.currentText()
        print(product)
        subproducts = Search.get_subproduct_list_of_product(self, product)
        print(subproducts)
        self.dlg.subproducts_comboBox.addItems(subproducts) 


    def radio_btn_state(self, b, dt1, dt2):
        """
        Enables and disables the date and hour picker widgets when
        the radio buttons are selected.
        :param b: The radio button for single time step - self.dlg.single_radioButton
        :param dt1: The data and time picker for the start - self.dlg.dateTimeEdit_1
        :param dt2: The date and time picker for the end - self.dlg.dateTimeEdit_2
        :return:
        """
        # If single radio button (b) is checked, then enable 1 datetime widget box
        if b.isChecked() == True:
            dt1.setDisabled(False)
            dt2.setDisabled(True)
            #print (b.text()+" is selected")
        else:
            # Multi radio button is checked, so enable both datetime widget boxes
            dt1.setDisabled(False)
            dt2.setDisabled(False)
            #print (b.text()+" is deselected")
    
    def get_data_from_datacube_nesw(self, product, subproduct, north, east, south, west, start, end):
        """
        The request sent to the datacube to process the data given the key file.
        :param product: The name of the product
        :param subproduct: The name of the subproduct
        :param north: The name of the north point
        :param east: The name of the east point
        :param south: The name of the south point
        :param west: The name of the west point
        :param start: The start date
        :param end: The end date
        :return:
        """

        # Get key_file location with access to the datacube to get_data from Dataset.py
        key_file = self.dlg.lineEdit.displayText()
        print(f"key_file location: {key_file}")
    
        # Using DQTools
        query = Dataset(product=product, subproduct=subproduct, region=None, tile=None, res=None, key_file=key_file)
        region = [north, east, south, west]
        query.get_data(start = start, stop=end, region=region, tile=None, res=None,)

        # Return an Xarray
        return query.data
    
    def create_raster_file(self, product, subproduct, north, east, south, west, y):
        """
        This prepares and creates the path where the Xarray writes to netcdf file, 
        which can be added as a Raster layer.
        :param product: The name of the product
        :param subproduct: The name of the subproduct
        :param north: The name of the north point
        :param east: The name of the east point
        :param south: The name of the south point
        :param west: The name of the west point
        :param start: The start date
        :param end: The end date
        :param y: The Xarray outputted from the datacube request
        :return:
        """

        # Re-formats the start and end dates and hour for filename
        start_datetime = self.dlg.dateTimeEdit_1.dateTime().toString("yyyyMMdd_HH")
        end_datetime = self.dlg.dateTimeEdit_2.dateTime().toString("yyyyMMdd_HH")

        # Create filename and find its path
        filename = "%s_%s_N%d_E%d_S%d_W%d_%s_%s" % (product, subproduct, north, east, south, west, start_datetime, end_datetime)
        #default_temp_path = f"{tempfile.gettempdir()}/{filename}.nc"
        a = (self.dlg.lineEdit_2.displayText())
        b = (f"{filename}.nc")
        default_temp_path = os.path.join(a, b)

        # Write Xarray to netcdf
        y.to_netcdf(default_temp_path)

        # Creates new layer and adds to current project
        self.iface.addRasterLayer(default_temp_path, "%s_%s_N%d_E%d_S%d_W%d_%s_%s" % (product, subproduct, north, east, south, west, start_datetime, end_datetime))

    
    def run(self):
        """
        This prepares the user interface of the plugin and the performs the events 
        once "OK" is clicked.
        :return:
        """
            
        # Reloading the plugin
        reloadPlugin('assimila_datacube')

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = AssimilaDatacCubeDialog(self.iface)

        # Clears the values from previous run
        self.dlg.lineEdit.clear() #keyfile
        self.dlg.lineEdit_2.clear() #rasterfile

        # Displays key file path location
        #self.key_file = os.path.join(os.path.dirname(__file__), ".assimila_dq")
        self.key_file = os.path.join(expanduser("~"), "Documents", ".assimila_dq") # default location
        self.dlg.lineEdit.insert(self.key_file)

        # Display default raster file path location
        """ 
            Not using temporary location due to permissioin error if you
            read the path from the lineEdit. Use tempfile.gettempdir to 
            access temporary directory without permission error. 
            raster_file = "Users\Jenny\AppData\Local\Temp"
            #default_temp_path = f"{tempfile.gettempdir()}/{filename}.nc"
        """
        raster_file = os.path.join(expanduser("~"), "Documents")
        self.dlg.lineEdit_2.insert(raster_file)

        # Display dropdowns for products
        # Only runs on the first run as the products_comboBox is empty
        # Instead of clearing the products combobox and then appending everytime
        # Only searches for products once despite the number of times the plugin is run
        if self.dlg.products_comboBox.currentIndex() == -1:
            products = Search.products().name.tolist()
            self.dlg.products_comboBox.setDuplicatesEnabled(False) 
            self.dlg.products_comboBox.addItems(products)
        
        # Display dropdown for subproducts
        self.dlg.subproducts_comboBox.addItem('rfe') # Defaulting 1st item Subprodusct is 'rfe'
        """ Issue: for nth run, perform nth subproduct_selectionchange """
        self.dlg.products_comboBox.currentTextChanged.connect(self.subproduct_selectionchange) # For updating the subproduct
        self.dlg.subproducts_comboBox.removeItem(1) # Removing default subproduct value of 'rfe'

        # Links the Radio buttons and datetime widgets
        self.dlg.multi_radioButton.toggled.connect(lambda: self.radio_btn_state(self.dlg.single_radioButton, self.dlg.dateTimeEdit_1, self.dlg.dateTimeEdit_2))

        # Show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        # Runs when OK button is pressed
        if result:

            # runs process using values in widgets
            product = (self.dlg.products_comboBox.currentText()).lower()
            print(f"The product being run is {product}")
            subproduct = self.dlg.subproducts_comboBox.currentText()
            print(f"The subproduct being run is {subproduct}")
            north = self.dlg.N_spinBox.value()
            print('N: ' + str(north))
            east = self.dlg.E_spinBox.value()
            print('E: ' + str(east))
            south = self.dlg.S_spinBox.value()
            print('S: ' + str(south))
            west = self.dlg.W_spinBox.value()
            print('W: ' + str(west))

            # Format start and end dates and hour for datecube
            start = self.dlg.dateTimeEdit_1.dateTime().toString("yyyy-MM-ddTHH:00:00")
            if self.dlg.single_radioButton.isChecked():
                end = start
                # Perform check method for d1
                self.check(north, east, south, west, self.dlg.dateTimeEdit_1.dateTime(), self.dlg.dateTimeEdit_1.dateTime())
            else: 
                end = self.dlg.dateTimeEdit_2.dateTime().toString("yyyy-MM-ddTHH:00:00")
                # Perform check method for d1 d2
                self.check(north, east, south, west, self.dlg.dateTimeEdit_1.dateTime(), self.dlg.dateTimeEdit_2.dateTime())
            
            print(start)
            print(end)

            # Get Xarray from datacube
            y = self.get_data_from_datacube_nesw(product, subproduct, north, east, south, west, start, end)

            # Write Xarray to file
            self.create_raster_file(product, subproduct, north, east, south, west, y)

            pass



            
