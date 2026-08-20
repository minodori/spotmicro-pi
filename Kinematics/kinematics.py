import numpy as np
from math import *
import random

# matplotlib 은 그릴 때만 불러온다.
#
# 예전에는 모듈 최상위에서 import 하고 `fig = plt.figure()` 까지 실행했다.
# 이 파일은 실측 링크 상수(l1~l4, L, W)와 IK 를 담고 있어 시뮬레이터·학습 코드가
# 반드시 import 하는데, 그때마다 다음 일이 벌어졌다:
#   - matplotlib 이 없는 환경에서는 import 자체가 실패한다
#   - 학습 환경을 병렬로 띄우면 프로세스마다 figure 를 만든다 (헤드리스에서 백엔드 문제)
#   - `np.random.rand(2,25)` 가 전역 난수 상태를 소비해 시드 재현성을 깬다
# 상수를 읽으려고 import 했을 뿐인데 부작용이 따라오면 안 된다.
def _plt():
    import matplotlib.pyplot as plt
    return plt


def setupView(limit):
    plt = _plt()
    ax = plt.axes(projection="3d")
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_zlim(-limit, limit)
    ax.set_xlabel("X")
    ax.set_ylabel("Z")
    ax.set_zlabel("Y")
    return ax

class Kinematic:

    def __init__(self):
        # 실측. 원본 공개값 l1=50 l2=20 l3=100 l4=100 L=140 W=75 는 실물과 크게
        # 달라 IK 가 계산한 발끝 위치 자체가 틀렸다.
        # 다리 전체 길이가 200 -> 245mm (1.23배), 몸통 앞뒤가 140 -> 185mm.
        #
        #   l1  어깨축 -> Upper축, 좌우 성분   : 앞발 트랙폭 190mm 에서 역산 (W+2*l1)
        #   l2  어깨축 -> Upper축, 수직 성분   : 어깨축~발바닥 240 - Upper축~발바닥 220
        #   l3  Upper축 -> 무릎축 (대퇴부)     : 아래 2026-08-21 재실측 참조
        #   l4  무릎축 -> 발바닥 (하퇴부)      : STL 원피팅 131 + 미끄럼방지 패드 3
        #   L   앞뒤 어깨축 간격               : 실측. URDF(186)와 일치
        #   W   좌우 어깨축 간격               : STL 어깨 브래킷, 원피팅 오차 0.000
        #
        # l3/l4 는 회전축에 수직인 평면(사지 평면)에서의 거리다. 두 축이 평행하므로
        # 축 방향 성분은 포함하지 않는다.
        # 2026-08-21 재실측. l3 을 125 -> 110, l4 를 138 -> 135 로 내렸다.
        #
        # 8/19 에 넣은 125 는 블렌더 측면도에서 읽은 값이었는데, 독립된 세 방법이
        # 그보다 짧다고 말한다:
        #     Fusion 측정        110
        #     STL 원피팅         109.9 (l3) / 131 (l4)
        #     실물 줄자          대퇴축~발바닥 245  (= 110 + 135)
        # 코드의 263 은 실물보다 18mm 길었다. §6.25 에서 한 번 고친 곳을 다시 고치는
        # 셈인데, 그때는 "너무 짧다" 를 고쳤고 이번엔 "너무 길다" 를 고친다.
        #
        # 파급: 다리 최대 도달이 263 -> 245 로 줄어 몸통 높이 상한이 내려간다.
        # Upper축~발 거리 H = 120 + height 이므로 height <= 125 여야 도달 가능하다.
        # Common/gait_params.py 의 height 범위를 60~120 으로 좁혔다.
        self.l1=56
        self.l2=20
        self.l3=110
        self.l4=135

        self.L = 185
        self.W = 78
        
        #leg iterators. ex. LEG_BACK + LEG_LEFT -> array[2]
        self.LEG_FRONT = 0
        self.LEG_BACK = 2
        self.LEG_LEFT = 0
        self.LEG_RIGHT =1

        #thetas, which will be used on controllers
        self.thetas = np.array([[0, 0, 0],[0, 0, 0],[0, 0, 0],[0, 0, 0]], dtype=np.float64)

    def bodyIK(self,omega,phi,psi,xm,ym,zm):
        Rx = np.array([[1,0,0,0],
                    [0,np.cos(omega),-np.sin(omega),0],
                    [0,np.sin(omega),np.cos(omega),0],[0,0,0,1]])
        Ry = np.array([[np.cos(phi),0,np.sin(phi),0],
                    [0,1,0,0],
                    [-np.sin(phi),0,np.cos(phi),0],[0,0,0,1]])
        Rz = np.array([[np.cos(psi),-np.sin(psi),0,0],
                    [np.sin(psi),np.cos(psi),0,0],[0,0,1,0],[0,0,0,1]])
        Rxyz = Rx.dot(Ry.dot(Rz))

        T = np.array([[0,0,0,xm],[0,0,0,ym],[0,0,0,zm],[0,0,0,0]])
        Tm = T+Rxyz

        sHp=np.sin(pi/2)
        cHp=np.cos(pi/2)
        (L,W)=(self.L,self.W)

        return([Tm.dot(np.array([[cHp,0,sHp,L/2],[0,1,0,0],[-sHp,0,cHp,W/2],[0,0,0,1]])),
                Tm.dot(np.array([[cHp,0,sHp,L/2],[0,1,0,0],[-sHp,0,cHp,-W/2],[0,0,0,1]])),
                Tm.dot(np.array([[cHp,0,sHp,-L/2],[0,1,0,0],[-sHp,0,cHp,W/2],[0,0,0,1]])),
                Tm.dot(np.array([[cHp,0,sHp,-L/2],[0,1,0,0],[-sHp,0,cHp,-W/2],[0,0,0,1]]))])

    def legIK(self,point):
        (x,y,z)=(point[0],point[1],point[2])
        (l1,l2,l3,l4)=(self.l1,self.l2,self.l3,self.l4)
        try:        
            F=sqrt(x**2+y**2-l1**2)
        except ValueError:
            print("Error in legIK with x {} y {} and l1 {}".format(x,y,l1))
            F=l1
        G=F-l2  
        H=sqrt(G**2+z**2)
        theta1=-atan2(y,x)-atan2(F,-l1)
        
        D=(H**2-l3**2-l4**2)/(2*l3*l4)
        try:        
            theta3=acos(D) 
        except ValueError:
            print("Error in legIK with x {} y {} and D {}".format(x,y,D))
            theta3=0
        theta2=atan2(z,G)-atan2(l4*sin(theta3),l3+l4*cos(theta3))
        
        return(theta1,theta2,theta3)

    def calcLegPoints(self,angles):
        (l1,l2,l3,l4)=(self.l1,self.l2,self.l3,self.l4)
        (theta1,theta2,theta3)=angles
        theta23=theta2+theta3

        T0=np.array([0,0,0,1])
        T1=T0+np.array([-l1*cos(theta1),l1*sin(theta1),0,0])
        T2=T1+np.array([-l2*sin(theta1),-l2*cos(theta1),0,0])
        T3=T2+np.array([-l3*sin(theta1)*cos(theta2),-l3*cos(theta1)*cos(theta2),l3*sin(theta2),0])
        T4=T3+np.array([-l4*sin(theta1)*cos(theta23),-l4*cos(theta1)*cos(theta23),l4*sin(theta23),0])
            
        return np.array([T0,T1,T2,T3,T4])

    def drawLegPoints(self,p):
        plt = _plt()
        # draw basic position
        plt.plot([x[0] for x in p],[x[2] for x in p],[x[1] for x in p], 'k-', lw=3)
        
        #draw body points
        plt.plot([p[0][0]],[p[0][2]],[p[0][1]],'bo',lw=2)
        
        # draw end points
        plt.plot([p[4][0]],[p[4][2]],[p[4][1]],'ro',lw=2)    

    #edited by shson98
    def drawLegPair(self,Tl,Tr,Ll,Lr, LEG_FR):
        plt = _plt()
        Ix=np.array([[-1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        self.drawLegPoints([Tl.dot(x) for x in self.calcLegPoints(self.legIK(np.linalg.inv(Tl).dot(Ll)))])
        self.drawLegPoints([Tr.dot(Ix.dot(x)) for x in self.calcLegPoints(self.legIK(Ix.dot(np.linalg.inv(Tr).dot(Lr))))])
        
        # print(self.legIK(np.linalg.inv(Tl).dot(Ll)))
        self.thetas[LEG_FR+self.LEG_LEFT]=np.array(self.legIK(np.linalg.inv(Tl).dot(Ll)))

        # print(self.legIK(Ix.dot(np.linalg.inv(Tr).dot(Lr))))
        self.thetas[LEG_FR+self.LEG_RIGHT]=np.array(self.legIK(Ix.dot(np.linalg.inv(Tr).dot(Lr))))

    def drawRobot(self,Lp,angles,center):
        plt = _plt()
        (omega,phi,psi)=angles
        (xm,ym,zm)=center
        
        FP=[0,0,0,1]
        (Tlf,Trf,Tlb,Trb)= self.bodyIK(omega,phi,psi,xm,ym,zm)
        CP=[x.dot(FP) for x in [Tlf,Trf,Tlb,Trb]]

        CPs=[CP[x] for x in [0,1,3,2,0]]

        # draw body points with body edges
        plt.plot([x[0] for x in CPs],[x[2] for x in CPs],[x[1] for x in CPs], 'bo-', lw=2)

        self.drawLegPair(Tlf,Trf,Lp[0],Lp[1], self.LEG_FRONT)
        self.drawLegPair(Tlb,Trb,Lp[2],Lp[3], self.LEG_BACK)

    # La: Leg Angles
    def drawRobotbyAngles(self,La,angles,center):
        plt = _plt()
        Ix=np.array([[-1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        (omega,phi,psi)=angles
        (xm,ym,zm)=center
        
        FP=[0,0,0,1]
        (Tlf,Trf,Tlb,Trb)= self.bodyIK(omega,phi,psi,xm,ym,zm)
        CP=[x.dot(FP) for x in [Tlf,Trf,Tlb,Trb]]

        CPs=[CP[x] for x in [0,1,3,2,0]]

        # draw body points with body edges
        plt.plot([x[0] for x in CPs],[x[2] for x in CPs],[x[1] for x in CPs], 'bo-', lw=2)

        # Draw LEG_FRONT
        self.drawLegPoints([Tlf.dot(x) for x in self.calcLegPoints(tuple(La[0]))])
        self.drawLegPoints([Trf.dot(Ix.dot(x)) for x in self.calcLegPoints(tuple(La[1]))])

        # Draw LEG_BACK
        self.drawLegPoints([Tlb.dot(x) for x in self.calcLegPoints((tuple(La[2])))])
        self.drawLegPoints([Trb.dot(Ix.dot(x)) for x in self.calcLegPoints(tuple(La[3]))])

    def calcIK(self,Lp,angles,center):
        (omega,phi,psi)=angles
        (xm,ym,zm)=center
        
        (Tlf,Trf,Tlb,Trb)= self.bodyIK(omega,phi,psi,xm,ym,zm)

        Ix=np.array([[-1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        return np.array([self.legIK(np.linalg.inv(Tlf).dot(Lp[0])),
        self.legIK(Ix.dot(np.linalg.inv(Trf).dot(Lp[1]))),
        self.legIK(np.linalg.inv(Tlb).dot(Lp[2])),
        self.legIK(Ix.dot(np.linalg.inv(Trb).dot(Lp[3])))])

# Inverse Kinematics
def initIK(Lp):
    setupView(200).view_init(elev=12., azim=28)
    moduleKinematics = Kinematic()
    moduleKinematics.drawRobot(Lp,(0,0,0),(0,0,0))
    
    return moduleKinematics.thetas

# Forward Kinematics
def initFK(La):
    setupView(200).view_init(elev=12., azim=28)
    moduleKinematics = Kinematic()
    moduleKinematics.drawRobotbyAngles(La,(0,0,0),(0,0,0))

    return moduleKinematics.thetas

def update_lines(i, Lp, angles):
    initIK(Lp)

def animationKinecatics(Lp):
    angles=[0]
    from matplotlib.animation import FuncAnimation
    fig = _plt().figure()
    lines_ani = FuncAnimation(fig, update_lines, frames=1000, fargs=(Lp, angles), interval=100)
    _plt().show()
    
    return lines_ani

def plotKinematics():
    _plt().show()

if __name__=="__main__":
    Lp=np.array([[100,-100,100,1], \
                [100,-100,-100,1], \
                [-100,-100,100,1], \
                [-100,-100,-100,1]])

    # case #1
    '''
    La = [ [ 0.12074281628178252, -0.7609430170197956, 2.187424485337152 ],
        [ 0.12074281628178252, -0.7609430170197956, 2.187424485337152 ],
        [ 0.12074281628178252, -1.4264814683173563, 2.187424485337152 ],
        [ 0.12074281628178252, -1.4264814683173563, 2.187424485337152 ] ]
    '''
    # # case #2
    # # First 3 seconds position in simulation
    # La = [[-0.041886,   -0.65947755,  1.3189551 ], \
    #         [-0.041886,   -0.65947755,  1.3189551 ], \
    #         [-0.041886,   -0.82366283,  1.27219102], \
    #         [-0.041886,   -0.82366283,  1.27219102]]

    # # case #3
    # # All Zeros
    # La =   [[0,   0,  0 ], \
    #         [0,   0,  0 ], \
    #         [0,   0,  0 ], \
    #         [0,   0,  0]]

    # Pose Visualization

    initIK(Lp)
    # plotKinematics()

    # Or 

    # initFK(La)
    plotKinematics()