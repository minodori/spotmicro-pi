import time
import numpy as np
import math

class KinematicLegMotion:

    def __init__(self,LLp):
        self.rtime=time.time()
        self.running=False
        self.LLp=LLp

    def moveTo(self,newLLp,rtime,func=None):
        if self.running:
            # TODO: Queue the Requests
            print("Movement already running, please try again later.")
            return False
        self.startTime=time.time()
        self.startLLp=self.LLp
        self.func=func
        self.targetLLp=newLLp
        self.endTime=time.time()+rtime/1000
        self.running=True
        return True
    
    def update(self):
        diff=time.time()-self.startTime
        ldiff=self.targetLLp-self.startLLp
        tdiff=self.endTime-self.startTime
        ldiff/(tdiff*diff)
        p=1/tdiff*diff

        if time.time()>self.endTime and self.running:
            self.running=False
            p=1
        self.LLp=self.startLLp+ldiff*p
        if self.func:
            self.LLp=self.func(p,self.LLp)

    def step(self):
        if self.running:
            self.update()
        return self.LLp

class KinematicMotion:

    def __init__(self,Lp):
        self.Lp=Lp
        self.legs=[KinematicLegMotion(Lp[x]) for x in range(4)]

    def moveLegsTo(self,newLp,rtime):
        [self.legs[x].moveTo(newLp[x],rtime) for x in range(4)]

    def moveLegTo(self,leg,newLLp,rtime,func=None):
        return self.legs[leg].moveTo(newLLp,rtime,func)

    def step(self):
        return [x.step() for x in self.legs]


"""
This class will define the trotting-gait function
A complete cycle is tone in Tt
Each leg has the following "states"
0 - wait on ground for t0
1 - move on ground for steplength Sl for t1
2 - wait on ground for t2
3 - lift leg by Sh and Sl for t3 back to 0
"""
class TrottingGait:
    
    def __init__(self):
        self.step_gain = 0.8
        self.maxSl=2
        self.bodyPos=(0,100,0)
        self.bodyRot=(0,0,0)
        # t0/t2 는 발을 몸통 기준 고정 위치에 붙들어 두는 대기 구간이었다.
        # 같은 시각에 대각선 반대쪽 다리는 t1 에서 끌고 있으므로, 네 발이 모두
        # 접지한 상태에서 두 발은 정지하고 두 발은 움직이는 상황이 된다.
        # 이러면 반드시 미끄러진다. 접지한 발끼리 속도가 같아야 미끄러지지 않는다.
        # (접지 속도 편차: 300/1200/300/200 -> 15.5, 0/1200/0/200 -> 0.0)
        self.t0=0
        # t1/t3 의 비가 네 발 지지 비율을 정한다:
        #     네발지지 = (t1 - Tt/2) * 2 / Tt,  Tt = t1 + t3
        # 이 비율이 낮으면 대각선 두 발로만 버티는 구간이 길어지고, IMU 없는
        # 개루프에서는 그 구간에 무릎 하중이 두 배가 되어 밀리며 주저앉는다.
        # t3 만 400 으로 올렸다가 이 비율이 71.8% -> 50.2% 로 떨어져 주저앉았다.
        # t3 를 늘릴 때는 t1 을 반드시 같이 늘릴 것.
        self.t1=1200
        self.t2=0
        self.t3=200
        self.Sl=0.0
        self.Sw=0
        # 발 들어올림 높이. 스윙 t3 안에 Sh 를 올리고 보폭만큼 되돌려야 하므로
        # 무릎이 요구받는 각속도를 Sh 가 지배한다 (t3=200ms, 실측 링크 기준):
        #     Sh=20 -> 250도/s,  Sh=25 -> 313,  Sh=30 -> 375,  Sh=40 -> 501
        # DS3235 무부하 정격 545도/s (0.11s/60도). 링크 길이를 실측값으로 바로잡으면서
        # 같은 수직 이동에 필요한 무릎 회전이 줄어 여유가 늘었다
        # (구 모델에서는 Sh=40 이 739도/s 로 정격을 넘었다).
        #
        # 순 전진 = |Sl| x (스윙 중 발이 실제로 떠 있는 비율) 이다. 발이 전혀 안 뜨면
        # 스탠스와 스윙이 정확히 상쇄되어 순 이동이 0 이 된다. 처짐이 Sh 를 잡아먹지
        # 않도록 하는 것이 이 값의 역할이다.
        self.Sh=20 #100
        self.Sa=0
        # 발의 기본 위치. 실측 치수(L=185, W=78, l1=56)에 맞춰 잡았다.
        #
        # bodyX=50 이므로 엉덩관절은 앞 x=+142.5, 뒤 x=-42.5 에 온다 (L/2=92.5).
        # 이전 값 Fo=120/Ro=50 은 L=140 을 가정한 것이어서 앞발이 관절보다 22.5mm 뒤,
        # 뒷발이 7.5mm 뒤에 놓였다. 그 비대칭이 전진/후진 차이를 만들었다.
        #
        # 지금 값은 거기서 다시 25mm 뒤로 옮긴 것이다 (관절 바로 아래는 142.5/42.5).
        # 이유는 무게중심이다. 트롯은 주기의 28.6% 를 대각선 두 발로만 버티고,
        # 그때 지지면은 두 발을 잇는 '선' 이다. 그 선이 중심선을 지나는 x 에
        # 무게중심이 있어야 넘어지지 않는다.
        #     발이 관절 바로 아래(142.5/42.5) -> 대각선 교차 x=50
        #     실측 무게중심 (앞 800g / 전체 2200g) -> Xcom = 24.8
        #     25mm 어긋나 있어 pitch 트림을 최대(10mm=16mm 전방)로 줘도 부족했다
        # 발을 25mm 뒤로 옮기면 대각선 교차가 24.8 로 내려와 무게중심과 일치한다.
        # 앞뒤를 같은 양만큼 옮기므로 대칭은 유지된다 (둘 다 관절보다 25mm 뒤).
        # 부수 효과로 무릎 모멘트 팔도 줄어든다 (h=110 에서 79.1 -> 68.7mm).
        #
        # 배터리·보드를 앞으로 옮겨 무게중심을 25mm 전진시키면 142.5/42.5 로
        # 되돌리는 것이 더 좋다 (다리가 수직이 되어 미는 힘이 가장 크다).
        #
        # Spf/Spr 은 어깨각이 0 이 되는 좌우 중립 위치 W/2 + l1 = 39 + 56 = 95.
        # 이전 값 87/77 은 W=75, l1=50 을 가정한 것이다. 앞뒤가 10mm 달라
        # 보행 시작 순간 발이 옆으로 튀는 원인이었다.
        self.Spf=95
        self.Spr=95
        self.Fo=117.5
        self.Ro=67.5

        self.Rc=[-50,0,0,1] # rotation center


    """
    calculates the Lp - LegPosition for the configured gait for time t and original Lp of x,y,z
    """
    def calcLeg(self,t,x,y,z,dy=0.0):
        # dy 는 이 다리만의 y 트림 (mm). 조립 오차로 다리 유효 길이가 다른 것을
        # 보정한다. 양수면 발끝이 몸통에 가까워져(다리가 짧아져) 스윙 중 지면
        # 여유가 늘고, 접지 중에는 그 코너의 하중·자세가 바뀐다.
        startLp=np.array([x-self.Sl/2.0,y+dy,z-self.Sw,1])
        endY=0 #-0.8 # delta y to jump a bit before lifting legs
        endLp=np.array([x+self.Sl/2,y+endY+dy,z+self.Sw,1])
        
        if(t<self.t0): # TODO: remove t0 and t2 - not practical
            return startLp
        elif(t<self.t0+self.t1): # drag foot over ground

            td=t-self.t0
            tp=td/self.t1   # 1/(t1/td) 와 동일하되 td==0 에서 ZeroDivisionError 가 나지 않는다
            diffLp=endLp-startLp
            curLp=startLp+diffLp*tp
            psi=-((math.pi/180*self.Sa)/2)+(math.pi/180*self.Sa)*tp
            Ry = np.array([[np.cos(psi),0,np.sin(psi),0],
                    [0,1,0,0],
                    [-np.sin(psi),0,np.cos(psi),0],[0,0,0,1]])
            #Tlm = np.array([[0,0,0,-self.Rc[0]],[0,0,0,-self.Rc[1]],[0,0,0,-self.Rc[2]],[0,0,0,0]])
            curLp=Ry.dot(curLp)
            return curLp
        elif(t<self.t0+self.t1+self.t2):
            return endLp
        elif(t<self.t0+self.t1+self.t2+self.t3): # Lift foot
            td=t-(self.t0+self.t1+self.t2)
            tp=td/self.t3   # 위와 동일한 이유
            diffLp=startLp-endLp
            curLp=endLp+diffLp*tp
            # 발 들어올림 프로파일.
            # sin(pi*tp) 는 tp=1(착지)에서 하강 속도가 최대가 되어 발이 꽂힌다.
            # Sh=20/t3=200 에서 314mm/s, Sh=40 이면 628mm/s 로 지면을 때린다.
            # 무릎이 이 충격을 정면으로 받아 혼이 반복해서 이탈했다.
            # (1-cos(2pi*tp))/2 는 최고점과 소요 시간이 같고 최대 속도도 같지만,
            # 이착지 양쪽에서 수직 속도가 0 이다. 최대 속도가 스윙 중간으로 옮겨간다.
            curLp[1]+=self.Sh*(1-math.cos(2*math.pi*tp))/2
            return curLp
            
    def stepLength(self,len):
        self.Sl=len

    def positions(self,t,kb_offset={}):
        spf=self.Spf
        spr=self.Spr
        # self.Sh=60.0

        if list(kb_offset.values()) == [0.0, 0.0, 0.0]:
            self.Sl=0.0
            self.Sw=0.0
            self.Sa=0.0
        else:
            self.Sl=kb_offset['IDstepLength']
            self.Sw=kb_offset['IDstepWidth']
            self.Sa=kb_offset['IDstepAlpha']

        Tt=(self.t0+self.t1+self.t2+self.t3)
        Tt2=Tt/2
        rd=0 # rear delta - unused - maybe stupid
        td=(t*1000)%Tt
        t2=(t*1000-Tt2)%Tt
        rtd=(t*1000-rd)%Tt # rear time delta
        rt2=(t*1000-Tt2-rd)%Tt
        Fx=self.Fo
        Rx=-1*self.Ro
        Fy=-100
        Ry=-100
        # 다리별 y 트림. 순서는 서보 인덱스와 같다: 0 FL, 1 FR, 2 RL, 3 RR
        tr=kb_offset.get('IDtrim',(0.0,0.0,0.0,0.0))
        r=np.array([self.calcLeg(td,Fx,Fy,spf,tr[0]),self.calcLeg(t2,Fx,Fy,-spf,tr[1]),self.calcLeg(rt2,Rx,Ry,spr,tr[2]),self.calcLeg(rtd,Rx,Ry,-spr,tr[3])])
        #print(r)
        return r
