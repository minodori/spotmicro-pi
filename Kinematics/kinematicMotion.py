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
        #
        # 그래서 이제 이 둘을 직접 만지지 않는다. 제어 루프가 매 주기
        # gait_params.gaitPhases() 로 Tt(주기)/duty(스윙 비율) 에서 환산해 넣는다.
        # 아래 값은 그 기본값(Tt 1400, duty 0.143)과 같고, 환산 없이 쓸 때의 값이다.
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
        # 위 표는 t3=200 일 때다. 슬루율은 Sh 가 아니라 Sh/t3 이 정하므로, t3 를 늘리면
        # 같은 Sh 를 내는 데 드는 무릎 각속도가 줄어든다 — 발을 같은 높이로 들되
        # 더 긴 시간에 걸쳐 들어올리기 때문이다. Sh=30/t3=400 은 188도/s 로
        # 지금(250)보다도 낮다.
        # 그래서 Sh 상한을 40 까지 열어두되, 올릴 때는 duty 를 같이 올려야 한다.
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

        # 보행 위상 (0~1). 절대시각의 나머지연산 대신 이걸 누적한다.
        # 주기 Tt 를 실시간으로 바꾸는 순간 (t*1000)%Tt 는 값이 튄다 —
        # 예를 들어 t=10s 에서 Tt 를 1400 -> 1500 으로 올리면 td 가 600 -> 1000 으로
        # 건너뛰어 다리가 접지 도중에 스윙으로 순간이동한다. 위상을 누적하면
        # Tt 가 바뀌어도 다리는 있던 자리에 그대로 있고 속도만 달라진다.
        self._phase=0.0
        self._lastT=None


    def yawRotate(self,Lp,psiDeg):
        """발끝을 몸통 y 축(연직) 둘레로 psiDeg 만큼 돌린다. 제자리 회전 보행에 쓴다.

        접지와 스윙이 같은 함수를 쓰게 하려고 뽑아냈다. 둘 중 한쪽에만 있으면
        구간 전환점에서 발이 순간이동한다.
        """
        psi=math.pi/180*psiDeg
        Ry=np.array([[np.cos(psi),0,np.sin(psi),0],
                     [0,1,0,0],
                     [-np.sin(psi),0,np.cos(psi),0],[0,0,0,1]])
        #Tlm = np.array([[0,0,0,-self.Rc[0]],[0,0,0,-self.Rc[1]],[0,0,0,-self.Rc[2]],[0,0,0,0]])
        return Ry.dot(Lp)

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
            # 접지 중 몸통이 Sa 만큼 돌아야 하므로 발은 -Sa/2 에서 +Sa/2 로 쓸린다.
            return self.yawRotate(curLp,-self.Sa/2.0+self.Sa*tp)
        elif(t<self.t0+self.t1+self.t2):
            return endLp
        elif(t<self.t0+self.t1+self.t2+self.t3): # Lift foot
            td=t-(self.t0+self.t1+self.t2)
            tp=td/self.t3   # 위와 동일한 이유
            diffLp=startLp-endLp
            curLp=endLp+diffLp*tp
            # 스윙에도 같은 회전을 적용한다. 예전에는 접지 구간에만 있어서, 접지는
            # +Sa/2 에서 끝나는데 스윙은 회전 없는 점에서 시작해 전환점마다 발이 튀었다
            # (Sa=3 에서 3.8mm, Sa=9 에서 11mm - 발 들어올림 20mm 에 육박한다).
            # 스윙은 되돌아오는 구간이므로 +Sa/2 -> -Sa/2 로, 접지와 반대 방향이다.
            curLp=self.yawRotate(curLp,self.Sa/2.0-self.Sa*tp)
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

    def advancePhase(self,t,Tt):
        """경과 시각 t(초) 로부터 위상을 누적해 0~Tt 범위의 주기 내 시각을 돌려준다.

        보행을 멈췄다 다시 시작하면 dt 가 몇 초씩 벌어진다. 그대로 더하면 위상이
        임의의 곳으로 튀므로, 한 주기를 넘는 간격은 "멈춰 있었다" 로 보고 버린다.
        멈춘 자리에서 이어서 걷게 된다.
        """
        if self._lastT is None:
            self._lastT=t
        dt=t-self._lastT
        self._lastT=t
        if 0.0 < dt < Tt/1000.0:
            self._phase=(self._phase+dt*1000.0/Tt)%1.0
        return self._phase*Tt

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
        # 절대시각의 나머지가 아니라 누적 위상을 쓴다. Tt 를 실시간으로 바꿔도
        # 다리가 있던 자리에 남는다 (advancePhase 주석 참조).
        pt=self.advancePhase(t,Tt)
        td=pt%Tt
        t2=(pt-Tt2)%Tt
        rtd=(pt-rd)%Tt # rear time delta
        rt2=(pt-Tt2-rd)%Tt
        Fx=self.Fo
        Rx=-1*self.Ro
        Fy=-100
        Ry=-100
        # 다리별 y 트림. 순서는 서보 인덱스와 같다: 0 FL, 1 FR, 2 RL, 3 RR
        tr=kb_offset.get('IDtrim',(0.0,0.0,0.0,0.0))
        r=np.array([self.calcLeg(td,Fx,Fy,spf,tr[0]),self.calcLeg(t2,Fx,Fy,-spf,tr[1]),self.calcLeg(rt2,Rx,Ry,spr,tr[2]),self.calcLeg(rtd,Rx,Ry,-spr,tr[3])])
        #print(r)
        return r
