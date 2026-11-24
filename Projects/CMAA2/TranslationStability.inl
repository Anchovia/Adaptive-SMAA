// Validation harness for the translation stability check (validation/improved-smaa-demo-translation-stability only).
// Pure camera translation as the demo's free-flight controller produces it with one key held (A/D strafe or Q/E
// up/down, movement speed 20, no Shift/Ctrl): the same acceleration (0.3 -> 1.0 over 1.4 s) and input smoothing
// (1 - exp(-200 dt)). The orientation stays at the flythrough pose of play time 2.0 (the start of the c28-c31
// captures, roll removed by the controller).

// vaCameraControllerFreeFlight movement with one key held or released.
struct TranslationKeyboard {
    float accel=0.0f;vaVector3 accum=vaVector3(0.0f,0.0f,0.0f);
    vaVector3 Step(float dt,bool held,const vaVector3& dir) {
        const float k=vaMath::TimeIndependentLerpF(dt,200.0f);
        accel=held?vaMath::Min(accel+dt*0.5f,1.0f):0.0f;
        const float moveSpeed=20.0f*dt*(0.3f+0.7f*accel);
        if(held)accum+=dir*moveSpeed;
        const vaVector3 move=accum*k;accum=accum*(1.0f-k);return move;
    }
};

// The free-flight controller's right and up axes for an orientation (its yaw/pitch extraction and rounding).
static void TranslationAxes(const vaQuaternion& ori,vaVector3& right,vaVector3& up) {
    const vaMatrix4x4 base=vaMatrix4x4::RotationZ(VA_PIf*0.5f)*vaMatrix4x4::RotationY(VA_PIf*0.5f);
    vaMatrix4x4 debased=base.Inverse()*vaMatrix4x4::FromQuaternion(ori);
    float yaw,pitch,roll;debased.DecomposeRotationYawPitchRoll(yaw,pitch,roll);
    const float k=100000.0f;yaw=vaMath::Round(yaw*k)/k;pitch=vaMath::Round(pitch*k)/k;
    const vaMatrix4x4 world=vaMatrix4x4::FromYawPitchRoll(yaw,pitch,0.0f);
    right=world.GetAxisY();up=world.GetAxisZ();
}

// Puts the camera at a pose under the free-flight controller (re-attaching makes it take the orientation).
static void TranslationSetPose(CMAA2Sample& sample,const vaVector3& pos,const vaQuaternion& ori) {
    auto& camera=sample.Camera();
    camera->AttachController(nullptr);camera->SetPosition(pos);camera->SetOrientation(ori);
    camera->AttachController(sample.GetFreeFlightControllerForValidation());
}

// -translationCapture "<bistro|minecraft> <h|v|y> <dt csv> <output dir> [start play time]": fixed 1920x1061 hidden window.
// h/v translate; y is a control without translation: yaw at a constant 0.4 rad/s from the same pose. The start pose is
// the flythrough pose at the given play time (default 2.0). A sixth token "velocity" keeps only Off and On and saves the
// camera velocity of On (velocity_XXXXX.dds) at every saved frame of fixed60 and fixed300. For each dt
// condition (fixed60: 1/60 s; fixed300: 1/300 s; fixedmean: the mean of the recorded window; recorded: 0.5 s of frame
// times recorded in the real demo, from row 300 of the csv) and each mode, history reset and 30 still frames at the
// start pose, then 0.5 s of translation. Saved: frame 0 (last still frame) and the motion frames from 0.4 s on, plus
// the frame before them (fixed60: every motion frame). Modes: Off (Temporal off =
// Adaptive SMAA 1X), On (Cross5, the demo), Fixed08, Official1Tap, WeightDebug (Cross5 weights as colour), SSRef (the
// demo's SuperSampleReference at the same pose). The app tick uses the same dt as the camera.
class BenchItemTranslationStability : public AutoBenchToolWorkItem {
    struct Mode {const char *name; bool ssref,temporal; int variant;};
    struct Cond {std::string name; std::vector<float> dt; float mean; int saveFrom;};
    std::vector<Mode> m_modes={{"Off",false,false,0},{"On",false,true,0},{"Fixed08",false,true,1},{"Official1Tap",false,true,2},
                               {"WeightDebug",false,true,3},{"SSRef",true,false,0}};
    std::vector<Cond> m_conds;
    bool m_minecraft,m_vertical,m_yaw,m_velocityDump,m_started=false,m_poseReady=false,m_done=false,m_failed=false,m_rendered=false;
    int m_mode=0,m_cond=0,m_frame=0;
    static const int c_pre=30;
    double m_lastProgress=0;float m_startTime;float m_time=0.0f;
    std::wstring m_output,m_dtPath;
    std::string m_cameraLog;
    vaVector3 m_startPos,m_pos,m_right,m_up;vaQuaternion m_startOri;
    TranslationKeyboard m_keyboard;
    int Count() const {return int(m_conds[m_cond].dt.size());}
    std::wstring Dir() const {return m_output+vaStringTools::SimpleWiden(m_conds[m_cond].name)+L"/"+vaStringTools::SimpleWiden(m_modes[m_mode].name)+L"/";}
    bool LoadDt(AutoBenchTool& tool) {
        FILE* f=nullptr;if(_wfopen_s(&f,m_dtPath.c_str(),L"rb")!=0||!f){tool.ReportAddText("Cannot open the dt csv.\r\n");return false;}
        std::vector<float> rows;char line[256];
        while(fgets(line,sizeof(line),f)){int i;float dt;if(sscanf_s(line,"%d,%f",&i,&dt)==2)rows.push_back(dt);}
        fclose(f);
        Cond rec{"recorded",{},0.0f,1};double sum=0;
        for(size_t i=300;i<rows.size()&&sum<0.5;i++){rec.dt.push_back(rows[i]);sum+=rows[i];}
        if(sum<0.5){tool.ReportAddText("The dt csv is too short.\r\n");return false;}
        rec.mean=float(sum/rec.dt.size());
        Cond mean{"fixedmean",std::vector<float>(size_t(std::lround(0.5/rec.mean)),rec.mean),rec.mean,1};
        Cond f60{"fixed60",std::vector<float>(30,1.0f/60.0f),1.0f/60.0f,1};
        Cond f300{"fixed300",std::vector<float>(150,1.0f/300.0f),1.0f/300.0f,1};
        m_conds={f60,f300,mean,rec};
        for(size_t c=1;c<m_conds.size();c++){double t=0;size_t i=0;for(;i<m_conds[c].dt.size()&&t<0.4-1e-6;i++)t+=m_conds[c].dt[i];m_conds[c].saveFrom=int(i)+1;}
        for(const auto& c:m_conds){double s=0;float lo=1,hi=0;for(float d:c.dt){s+=d;lo=vaMath::Min(lo,d);hi=vaMath::Max(hi,d);}
            tool.ReportAddRowValues({"dt_condition",c.name,std::to_string(c.dt.size()),std::to_string(c.saveFrom),vaStringTools::Format("%.6f",s),vaStringTools::Format("%.6f",c.mean),vaStringTools::Format("%.6f",lo),vaStringTools::Format("%.6f",hi)});}
        return true;
    }
    void Configure() {
        const auto& c=m_modes[m_mode];auto s=m_parent.GetSMAA();
        s->CleanupTemporaryResources();
        s->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
        m_parent.Settings().CurrentAAOption=c.ssref?CMAA2Sample::AAType::SuperSampleReference:CMAA2Sample::AAType::SMAA_AdaptiveTemporal;
        s->SetTemporalEnabled(c.temporal);s->SetResolveVariant(c.variant);s->ResetTemporalHistory();
        TranslationSetPose(m_parent,m_startPos,m_startOri);
        m_frame=-c_pre;m_rendered=false;m_keyboard=TranslationKeyboard();m_pos=m_startPos;m_time=0.0f;
        m_lastProgress=m_parent.GetApplication().GetTimeFromStart();
    }
    void Finish(AutoBenchTool& tool) {
        FILE* f=nullptr;if(_wfopen_s(&f,(m_output+L"camera.csv").c_str(),L"wb")==0&&f){fputs("condition,frame,dt,x,y,z\r\n",f);fputs(m_cameraLog.c_str(),f);fclose(f);}
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
        m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemTranslationStability(CMAA2Sample& parent,bool minecraft,bool vertical,bool yaw,float startTime,bool velocityDump,std::wstring dtPath,std::wstring output):
        AutoBenchToolWorkItem(parent),m_minecraft(minecraft),m_vertical(vertical),m_yaw(yaw),m_velocityDump(velocityDump),m_startTime(startTime),m_output(output),m_dtPath(dtPath) {
        if(velocityDump)m_modes={{"Off",false,false,0},{"On",false,true,0}};
    }
    void Tick(AutoBenchTool& tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(m_done)return;
        if(!m_started) {
            m_started=true;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::SMAA_AdaptiveTemporal;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();
            tool.ReportAddText(std::string("Translation stability capture. Scene: ")+(m_minecraft?"minecraft":"bistro")+", direction: "+(m_yaw?"yaw control 0.4 rad/s":(m_vertical?"vertical (Q/E, camera up)":"horizontal (A/D, camera right)"))+vaStringTools::Format(", start play time %.3f",m_startTime)+"\r\n");
            tool.ReportAddText("Free-flight key emulation (speed 20, acceleration, smoothing), start pose = flythrough play time 2.0, 30 still frames after a history reset, then 0.5 s of motion; frames 0 (still) .. N saved. Auto exposure adapts instantly.\r\n");
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            m_output+=std::wstring(L"/translation/")+(m_minecraft?L"minecraft_":L"bistro_")+(m_yaw?L"y/":(m_vertical?L"v/":L"h/"))+report.substr(report.find_last_of(L"\\/")+1)+L"/";
            vaFileTools::EnsureDirectoryExists(m_output);
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});
            if(!LoadDt(tool)){m_failed=true;Finish(tool);return;}
            m_parent.SetFlythroughCameraEnabled(true);m_parent.GetFlythroughCameraController()->SetPlaySpeed(0.0f);
            m_parent.GetFlythroughCameraController()->SetPlayTime(m_startTime);
            m_lastProgress=now;return;
        }
        if(!m_rendered){if(now-m_lastProgress>120){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
        m_rendered=false;m_lastProgress=now;
        if(!m_poseReady) {
            // The camera has been ticked at the flythrough pose; switch to the free-flight controller there.
            m_poseReady=true;m_startPos=m_parent.Camera()->GetPosition();m_startOri=m_parent.Camera()->GetOrientation();
            TranslationAxes(m_startOri,m_right,m_up);
            m_parent.SetFlythroughCameraEnabled(false);
            tool.ReportAddRowValues({"start_pose",vaStringTools::Format("%.5f %.5f %.5f",m_startPos.x,m_startPos.y,m_startPos.z),
                vaStringTools::Format("%.5f %.5f %.5f %.5f",m_startOri.x,m_startOri.y,m_startOri.z,m_startOri.w),
                vaStringTools::Format("right %.5f %.5f %.5f",m_right.x,m_right.y,m_right.z),vaStringTools::Format("up %.5f %.5f %.5f",m_up.x,m_up.y,m_up.z)});
            Configure();
        }else if(++m_frame>Count()) {
            if(++m_mode==int(m_modes.size())){m_mode=0;if(++m_cond==int(m_conds.size())){Finish(tool);return;}}
            Configure();
        }
        const Cond& c=m_conds[m_cond];
        const float dt=m_frame<=0?c.mean:c.dt[m_frame-1];
        if(m_yaw) {
            if(m_frame>=1)m_time+=dt;
            const vaMatrix4x4 base=vaMatrix4x4::RotationZ(VA_PIf*0.5f)*vaMatrix4x4::RotationY(VA_PIf*0.5f);
            vaMatrix4x4 debased=base.Inverse()*vaMatrix4x4::FromQuaternion(m_startOri);float yaw,pitch,roll;debased.DecomposeRotationYawPitchRoll(yaw,pitch,roll);
            TranslationSetPose(m_parent,m_startPos,vaQuaternion::FromRotationMatrix(base*vaMatrix4x4::FromYawPitchRoll(yaw+0.4f*m_time,pitch,0.0f)));
        }else {
            if(m_frame>=1)m_pos+=m_keyboard.Step(dt,true,m_vertical?m_up:m_right);
            m_parent.Camera()->SetPosition(m_pos);
        }
        m_parent.SetFixedDeltaTime(dt);
        if(m_mode==0&&m_frame>=1)m_cameraLog+=vaStringTools::Format("%s,%d,%.7f,%.6f,%.6f,%.6f\r\n",c.name.c_str(),m_frame,dt,m_pos.x,m_pos.y,m_pos.z);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;
        if(!m_poseReady)return;
        const auto& c=m_modes[m_mode];auto s=m_parent.GetSMAA();
        bool ok=m_parent.Settings().CurrentAAOption==(c.ssref?CMAA2Sample::AAType::SuperSampleReference:CMAA2Sample::AAType::SMAA_AdaptiveTemporal);
        if(!c.ssref)ok=ok&&s->GetAdaptiveSearch()&&s->GetSelectedTemporal()==c.temporal&&s->GetResolveVariant()==c.variant&&((s->GetPresentedOutputOverride()!=nullptr)==c.temporal);
        if(color->GetSizeX()!=1920||color->GetSizeY()!=1061)ok=false;
        if(!ok){tool.ReportAddRowValues({"failed_state",m_conds[m_cond].name,c.name,std::to_string(m_frame),"FAIL"});m_failed=true;}
        if(m_frame<0||(m_frame>0&&m_frame<m_conds[m_cond].saveFrom-1))return;
        const auto dir=Dir();vaFileTools::EnsureDirectoryExists(dir);
        if(!color->SaveToPNGFile(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d.png",m_frame)))){m_failed=true;tool.ReportAddRowValues({"failed_save",c.name,std::to_string(m_frame),"FAIL"});}
        if(m_velocityDump&&c.temporal&&(m_conds[m_cond].name=="fixed60"||m_conds[m_cond].name=="fixed300")&&
            !s->SaveVelocityForValidation(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("velocity_%05d.dds",m_frame)))){m_failed=true;tool.ReportAddRowValues({"failed_velocity",c.name,std::to_string(m_frame),"FAIL"});}
        if(m_frame==Count())tool.ReportAddRowValues({"segment",m_conds[m_cond].name,c.name,std::to_string(Count()),std::to_string(m_conds[m_cond].saveFrom-1),ok?"PASS":"FAIL"});
    }
    bool IsDone(AutoBenchTool&) const override {return m_done;}
    float GetProgress() const override {return float(m_cond*int(m_modes.size())+m_mode)/float(m_conds.size()*m_modes.size());}
};

static bool QueueTranslationStability(CMAA2Sample& parent,AutoBenchTool& tool) {
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()) {
        if(_wcsicmp(p.first.c_str(),L"translationCapture")!=0)continue;
        std::wistringstream input(p.second);std::wstring scene,direction,dtPath,output;float startTime=2.0f;std::wstring flag;input>>scene>>direction>>dtPath>>output;if(!(input>>startTime))startTime=2.0f;input>>flag;
        if((scene!=L"bistro"&&scene!=L"minecraft")||(direction!=L"h"&&direction!=L"v"&&direction!=L"y")||dtPath.empty()||output.empty()){VA_LOG_ERROR("Expected scene, h|v|y, dt csv, output path without spaces and an optional start time");return true;}
        tool.AddTask(std::make_shared<BenchItemTranslationStability>(parent,scene==L"minecraft",direction==L"v",direction==L"y",startTime,flag==L"velocity",dtPath,output));return true;
    }
    return false;
}

// -translationDtRecord "<bistro|minecraft> <output dir>" (called from ImprovedSmaaScreensTick, without AutoBench):
// the demo as the user runs it (visible window, UI on, SMAA Adaptive + Temporal at Ultra, Temporal on, VSync off, no
// frame limit) with the camera translating sideways from the flythrough pose of play time 2.0 by the same key
// emulation at the real frame time, switching direction every 0.5 s (key released, other key pressed). After 300
// frames it writes 1800 frame times (the app's deltaTime of each frame, seconds) to dt.csv and quits.
struct TranslationDtRecorder {
    int state=0,frames=0;vaVector3 pos,right,up;vaQuaternion ori;TranslationKeyboard keyboard;float sinceSwitch=0;bool positive=true;
    std::vector<float> dts;std::wstring dir;
    // Returns true when done.
    bool Tick(CMAA2Sample& s,float lastDeltaTime) {
        ++frames;
        if(state==0) {s.SetFlythroughCameraEnabled(true);s.GetFlythroughCameraController()->SetPlaySpeed(0.0f);s.GetFlythroughCameraController()->SetPlayTime(2.0f);state=1;return false;}
        if(state==1) {if(frames<60)return false;
            pos=s.Camera()->GetPosition();ori=s.Camera()->GetOrientation();TranslationAxes(ori,right,up);
            s.SetFlythroughCameraEnabled(false);TranslationSetPose(s,pos,ori);state=2;frames=0;return false;}
        sinceSwitch+=lastDeltaTime;
        if(sinceSwitch>=0.5f){sinceSwitch=0;positive=!positive;keyboard.accel=0.0f;}
        pos+=keyboard.Step(lastDeltaTime,true,positive?right:right*-1.0f);
        s.Camera()->SetPosition(pos);
        if(frames>300)dts.push_back(lastDeltaTime);
        if(dts.size()<1800)return false;
        FILE* f=nullptr;
        if(_wfopen_s(&f,(dir+L"/dt.csv").c_str(),L"wb")==0&&f){fputs("frame,dt\r\n",f);for(size_t i=0;i<dts.size();i++)fprintf(f,"%d,%.7f\r\n",int(i),dts[i]);fclose(f);}
        return true;
    }
};
