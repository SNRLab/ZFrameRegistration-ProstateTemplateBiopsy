import os
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np

class ZFrameRegistrationScripted(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "ZFrameRegistration Scripted"
        self.parent.categories = ["IGT"]
        self.parent.dependencies = []
        self.parent.contributors = ["Junichi Tokuda (SPL), Longquan Chen (SPL), Christian Herz (SPL), Andriy Fedorov (SPL), Franklin King (SPL)"]
        self.parent.helpText = """
            This module performs Z-frame registration for image-guided interventions.
            It supports both 7-fiducial and 9-fiducial Z-frame configurations.
            """
        self.parent.acknowledgementText = """
            
            """
        moduleDir = os.path.dirname(self.parent.path)
        for iconExtension in ['.svg', '.png']:
            iconPath = os.path.join(moduleDir, 'Resources/Icons', self.__class__.__name__ + iconExtension)
            if os.path.isfile(iconPath):
                parent.icon = qt.QIcon(iconPath)
                break

class ZFrameRegistrationScriptedWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        self.logic = ZFrameRegistrationScriptedLogic()
        
        # Parameters Area
        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Parameters"
        self.layout.addWidget(parametersCollapsibleButton)
        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)
        
        # Input volume selector
        self.inputSelector = slicer.qMRMLNodeComboBox()
        self.inputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.inputSelector.selectNodeUponCreation = True
        self.inputSelector.addEnabled = False
        self.inputSelector.removeEnabled = False
        self.inputSelector.noneEnabled = False
        self.inputSelector.showHidden = False
        self.inputSelector.showChildNodeTypes = False
        self.inputSelector.setMRMLScene(slicer.mrmlScene)
        self.inputSelector.setToolTip("Pick the input volume.")
        parametersFormLayout.addRow("Input Volume: ", self.inputSelector)
        self.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onInputVolumeSelected)
        
        # Z-frame configuration selector
        self.zframeConfigSelector = qt.QComboBox()
        self.zframeConfigSelector.addItems(["z001", "z002", "z003", "z004", "z005"])
        parametersFormLayout.addRow("Z-Frame Configuration: ", self.zframeConfigSelector)
        #self.zframeConfigSelector.connect("currentTextChanged(QString)", self.onZFrameConfigChanged)

        # Frame Topology Text Edit
        self.frameTopologyTextEdit = qt.QTextEdit()
        self.frameTopologyTextEdit.setReadOnly(False)
        self.frameTopologyTextEdit.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
        self.frameTopologyTextEdit.setMaximumHeight(40)
        parametersFormLayout.addRow("Frame Topology: ", self.frameTopologyTextEdit)

        # Initialize topology text for default selection
        #self.onZFrameConfigChanged(self.zframeConfigSelector.currentText)
        self.frameTopologyTextEdit.setText("[30.0, 30.0, -30.0], [-30.0, 30.0, -30.0], [-30.0, -30.0, -30.0], [0.0, -1.0, 1.0], [1.0, 0.0, 1.0], [0.0, 1.0, 1.0]")

        # Slice range
        self.sliceRangeWidget = slicer.qMRMLRangeWidget()
        self.sliceRangeWidget.decimals = 0
        self.sliceRangeWidget.minimum = 0
        self.sliceRangeWidget.maximum = 20  # Default range, will update when image is loaded
        self.sliceRangeWidget.minimumValue = 6
        self.sliceRangeWidget.maximumValue = 11
        self.sliceRangeWidget.singleStep = 1
        parametersFormLayout.addRow("Slice Range: ", self.sliceRangeWidget)
        self.onInputVolumeSelected(self.inputSelector.currentNode())
        
        # Output transform selector
        self.outputSelector = slicer.qMRMLNodeComboBox()
        self.outputSelector.nodeTypes = ["vtkMRMLLinearTransformNode"]
        self.outputSelector.selectNodeUponCreation = True
        self.outputSelector.addEnabled = True
        self.outputSelector.removeEnabled = True
        self.outputSelector.noneEnabled = True
        self.outputSelector.showHidden = False
        self.outputSelector.showChildNodeTypes = False
        self.outputSelector.setMRMLScene(slicer.mrmlScene)
        self.outputSelector.setToolTip("Pick the output transform")
        parametersFormLayout.addRow("Output Transform: ", self.outputSelector)
        
        # Apply Button
        self.applyButton = qt.QPushButton("Apply")
        self.applyButton.toolTip = "Run the Z-frame registration."
        self.applyButton.enabled = False
        parametersFormLayout.addRow(self.applyButton)
        self.applyButton.connect('clicked(bool)', self.onApplyButton)
        
        self.layout.addStretch(1)
        
    def onInputVolumeSelected(self, node):
        if node:
            dims = node.GetImageData().GetDimensions()
            self.sliceRangeWidget.minimum = 0
            self.sliceRangeWidget.maximum = dims[2]-1

    # def onZFrameConfigChanged(self, configName):
    #     """Update the topology text based on the selected Z-frame configuration"""
    #     topologyMap = {
    #         "z001": "7-fiducial configuration (standard)",
    #         "z002": "9-fiducial configuration with additional anterior fiducials",
    #         "z003": "9-fiducial configuration with additional posterior fiducials",
    #         "z004": "7-fiducial configuration (variant 1)",
    #         "z005": "7-fiducial configuration (variant 2)"
    #     }
        
    #     self.topologyTextEdit.plainText = topologyMap.get(configName, "Unknown configuration")

    def onApplyButton(self):
        try:
            self.logic.run(self.inputSelector.currentNode(),
                     self.outputSelector.currentNode(),
                     self.zframeConfigSelector.currentText,
                     self.sliceRangeWidget.minimumValue,
                     self.sliceRangeWidget.maximumValue)
        except Exception as e:
            slicer.util.errorDisplay("Failed to compute results: "+str(e))
            import traceback
            traceback.print_exc()

class ZFrameRegistrationScriptedLogic(ScriptedLoadableModuleLogic):
    def run(self, inputVolume, outputTransform, zframeConfig, startSlice, endSlice):
        """
        Run the Z-frame registration algorithm
        """
        logging.info('Processing started')
        
        if not inputVolume or not outputTransform:
            raise ValueError("Input volume or output transform is invalid")
            
        # Get image data
        imageData = inputVolume.GetImageData()
        if not imageData:
            raise ValueError("Input image is invalid")
            
        # Get image properties
        dimensions = imageData.GetDimensions()
        spacing = inputVolume.GetSpacing()
        origin = inputVolume.GetOrigin()
        directions = vtk.vtkMatrix4x4()
        inputVolume.GetIJKToRASDirectionMatrix(directions)
        
        # Create the RAS to LPS transform
        ras2lps = vtk.vtkMatrix4x4()
        ras2lps.Identity()
        ras2lps.SetElement(0,0,-1)
        ras2lps.SetElement(1,1,-1)
        
        # Create the image to world transform
        imageToWorld = vtk.vtkMatrix4x4()
        imageToWorld.Identity()
        for i in range(3):
            for j in range(3):
                imageToWorld.SetElement(i,j, spacing[j] * directions.GetElement(i,j))
            imageToWorld.SetElement(i,3, origin[i])
            
        # TODO: Implement the actual Z-frame registration algorithm here
        # This would need to be implemented based on the specific requirements
        # of your Z-frame detection and registration method
        
        # For now, we'll just set up the infrastructure
        
        if zframeConfig in ["z001", "z004", "z005"]:
            # 7-fiducial registration
            logging.info("Running 7-fiducial registration")
            # TODO: Implement 7-fiducial registration
        elif zframeConfig in ["z002", "z003"]:
            # 9-fiducial registration
            logging.info("Running 9-fiducial registration")
            # TODO: Implement 9-fiducial registration
        else:
            raise ValueError("Invalid Z-frame configuration")
            
        # For now, just set identity transform
        outputTransform.SetMatrixTransformToParent(vtk.vtkMatrix4x4())
        
        logging.info('Processing completed')
        
        return True

# class ZFrameRegistrationScriptedTest(ScriptedLoadableModuleTest):
#     def setUp(self):
#         slicer.mrmlScene.Clear(0)

#     def runTest(self):
#         self.setUp()
#         self.test_ZFrameRegistration1()

#     def test_ZFrameRegistration1(self):
#         self.delayDisplay("Starting the test")
        
#         # Get/create input data
#         import SampleData
#         inputVolume = SampleData.downloadFromURL(
#             nodeNames='MRHead',
#             fileNames='MR-Head.nrrd',
#             uris='https://github.com/Slicer/SlicerTestingData/releases/download/MD5/39b01631b7b38232a220007230624c8e',
#             checksums='MD5:39b01631b7b38232a220007230624c8e')[0]
#         self.delayDisplay('Finished with download and loading')
        
#         outputTransform = slicer.vtkMRMLLinearTransformNode()
#         slicer.mrmlScene.AddNode(outputTransform)
        
#         logic = ZFrameRegistrationScriptedLogic()
#         self.assertTrue(logic.run(inputVolume, outputTransform, "z001", 0, 10))
        
#         self.delayDisplay('Test passed!') 