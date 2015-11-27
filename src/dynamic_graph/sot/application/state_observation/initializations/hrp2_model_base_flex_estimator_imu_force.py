# Launch it with py ../robotViewerLauncher.py +compensater.py +appli.py 
import sys
import numpy as np
from numpy import *
from dynamic_graph import plug
import dynamic_graph.signal_base as dgsb

from dynamic_graph.sot.core import Stack_of_vector, MatrixHomoToPoseUTheta, OpPointModifier, Multiply_matrix_vector, MatrixHomoToPose
from dynamic_graph.sot.application.state_observation import DGIMUModelBaseFlexEstimation, PositionStateReconstructor, InputReconstructor

from dynamic_graph.sot.core.derivator import Derivator_of_Vector

from dynamic_graph.sot.core.matrix_util import matrixToTuple
from dynamic_graph.sot.application.state_observation import Calibrate


class HRP2ModelBaseFlexEstimatorIMUForce(DGIMUModelBaseFlexEstimation):
    def __init__(self, robot, name='flextimator2'):
        DGIMUModelBaseFlexEstimation.__init__(self,name)
        
        self.setSamplingPeriod(0.005)  
        self.robot = robot

        self.robot.dynamic.inertia.recompute(1)					      
        self.robot.dynamic.waist.recompute(1)	

        # Sensors stack
        self.sensorStackimu = Stack_of_vector (name+'SensorsIMU')
        plug(self.robot.device.accelerometer,self.sensorStackimu.sin1)
        plug(self.robot.device.gyrometer,self.sensorStackimu.sin2)
        self.sensorStackimu.selec1 (0, 3)
        self.sensorStackimu.selec2 (0, 3)
	self.calibration= Calibrate('calibration')
	plug(self.sensorStackimu.sout,self.calibration.imuIn)
	plug(self.robot.dynamic.com,self.calibration.comIn)			

        self.sensorStackforce = Stack_of_vector (name+'SensorsFORCE')
        plug(self.robot.device.forceLLEG,self.sensorStackforce.sin1)
        plug(self.robot.device.forceRLEG,self.sensorStackforce.sin2)
        self.sensorStackforce.selec1 (0, 6)
        self.sensorStackforce.selec2 (0, 6)

        self.sensorStack = Stack_of_vector (name+'Sensors')
        plug(self.calibration.imuOut,self.sensorStack.sin1)
        plug(self.sensorStackforce.sout,self.sensorStack.sin2)
        self.sensorStack.selec1 (0, 6)
        self.sensorStack.selec2 (0, 12)

	plug(self.sensorStack.sout,self.measurement);
        self.contactForces = self.sensorStack.sin2
      
        # Input reconstruction

		# IMU Vector
        self.inputPos = MatrixHomoToPoseUTheta(name+'InputPosition')
        plug(robot.frames['accelerometer'].position,self.inputPos.sin)
        self.robot.dynamic.createJacobian(name+'ChestJ_OpPoint','chest')	
        self.imuOpPoint = OpPointModifier(name+'IMU_oppoint')
        self.imuOpPoint.setEndEffector(False)
        self.imuOpPoint.setTransformation(matrixToTuple(np.linalg.inv(np.matrix(self.robot.dynamic.chest.value))*np.matrix(self.robot.frames['accelerometer'].position.value)))
        plug (self.robot.dynamic.chest,self.imuOpPoint.positionIN)			
        plug (self.robot.dynamic.signal(name+'ChestJ_OpPoint'),self.imuOpPoint.jacobianIN)
        self.inputVel = Multiply_matrix_vector(name+'InputVelocity')
        plug(self.imuOpPoint.jacobian,self.inputVel.sin1)
        plug(self.robot.device.velocity,self.inputVel.sin2)
        self.inputPosVel = Stack_of_vector (name+'InputPosVel')
        plug(self.inputPos.sout,self.inputPosVel.sin1)
        plug(self.inputVel.sout,self.inputPosVel.sin2)
        self.inputPosVel.selec1 (0, 6)
        self.inputPosVel.selec2 (0, 6)
        self.IMUVector = PositionStateReconstructor (name+'EstimatorInput')
        plug(self.inputPosVel.sout,self.IMUVector.sin)
        self.IMUVector.inputFormat.value  = '001111'
        self.IMUVector.outputFormat.value = '011111'
        self.IMUVector.setFiniteDifferencesInterval(2)

        	# CoM and derivatives
        self.com=self.robot.dynamic.com
        self.DCom = Multiply_matrix_vector(name+'DCom')
        plug(self.robot.dynamic.Jcom,self.DCom.sin1)
        plug(self.robot.device.velocity,self.DCom.sin2)
        self.comVectorIn = Stack_of_vector (name+'ComVectorIn')
        plug(self.com,self.comVectorIn.sin1)
        plug(self.DCom.sout,self.comVectorIn.sin2)
        self.comVectorIn.selec1 (0, 3)
        self.comVectorIn.selec2 (0, 3)
        self.comVector = PositionStateReconstructor (name+'ComVector')
        plug(self.comVectorIn.sout,self.comVector.sin)
        self.comVector.inputFormat.value  = '000101'
        self.comVector.outputFormat.value = '010101'  

		# Compute derivative of Angular Momentum
        self.angMomDerivator = Derivator_of_Vector('angMomDerivator')
        plug(self.robot.dynamic.angularmomentum,self.angMomDerivator.sin)
        self.angMomDerivator.dt.value = self.robot.timeStep          
        
        	# Concatenate with InputReconstructor entity
        self.inputVector=InputReconstructor(name+'inputVector')
        plug(self.comVector.sout,self.inputVector.comVector)
        plug(self.robot.dynamic.inertia,self.inputVector.inertia)
	plug(self.robot.dynamic.angularmomentum,self.inputVector.angMomentum)
	plug(self.angMomDerivator.sout,self.inputVector.dangMomentum)
        self.inputVector.dinertia.value=(0,0,0,0,0,0)
        plug(self.robot.dynamic.waist,self.inputVector.positionWaist)
        plug(self.IMUVector.sout,self.inputVector.imuVector)
        plug(self.contactNbr,self.inputVector.nbContacts)

        self.inputVector.setSamplingPeriod(robot.timeStep)
        self.inputVector.setFDInertiaDot(True)     
        plug(self.inputVector.input,self.input)
        self.robot.flextimator = self

        kfe=40000
        kfv=600
        kte=600
        ktv=60
        self.setKfe(matrixToTuple(np.diag((kfe,kfe,kfe))))
        self.setKfv(matrixToTuple(np.diag((kfv,kfv,kfv))))
        self.setKte(matrixToTuple(np.diag((kte,kte,kte))))
        self.setKtv(matrixToTuple(np.diag((ktv,ktv,ktv))))


