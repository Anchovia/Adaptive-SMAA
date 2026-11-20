// ReShade still harness (experiment/reshade-adaptive-smaa): the demo's own AA off, UI hidden, and three
// fixed camera poses of the capture timeline (play time 2.0, 3.0, 4.0 = frames 60, 120, 180). For each pose
// the harness renders 90 frames, writes <dir>/ready_<i>.txt and waits for <dir>/shot_<i>.txt, which the
// driving script writes after ReShade saved its screenshot of that pose. ReShade itself is not part of
// the build; it is injected as dxgi.dll in a separate copy of the executable folder.
class BenchItemReShadeStill : public AutoBenchToolWorkItem {
    bool m_minecraft,m_started=false,m_done=false,m_failed=false,m_rendered=false,m_waiting=false;
    int m_pose=0,m_frames=0;
    double m_start=0,m_waitStart=0;
    std::wstring m_dir;
    static constexpr float kPoses[3]={2.0f,3.0f,4.0f};
    std::wstring File(const wchar_t *kind,int pose) const {return m_dir+kind+std::to_wstring(pose)+L".txt";}
    void Finish(AutoBenchTool& tool) {
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
        m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemReShadeStill(CMAA2Sample& parent,bool minecraft,std::wstring dir):AutoBenchToolWorkItem(parent),m_minecraft(minecraft),m_dir(dir) {
        if(!m_dir.empty()&&m_dir.back()!=L'\\'&&m_dir.back()!=L'/')m_dir+=L"/";
    }
    void Tick(AutoBenchTool& tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(m_done)return;
        if(!m_started) {
            m_started=true;m_start=now;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::None;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            vaFileTools::EnsureDirectoryExists(m_dir);
            tool.ReportStart();
            tool.ReportAddText(std::string("ReShade still harness. Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nDemo AA None; UI hidden; fixed60; poses at flythrough play time 2.0/3.0/4.0 (capture frames 60/120/180); 90 frames per pose before the ready marker.\r\n");
            tool.ReportAddRowValues({"handshake_dir",vaStringTools::SimpleNarrow(m_dir)});
        }
        m_parent.GetFlythroughCameraController()->SetPlayTime(kPoses[m_pose]);
        if(now-m_start<5.0)return;
        if(m_waiting) {
            if(vaFileTools::FileExists(File(L"shot_",m_pose))) {
                tool.ReportAddRowValues({"pose",std::to_string(m_pose),vaStringTools::Format("%.1f",kPoses[m_pose]),"shot","PASS"});
                m_waiting=false;m_frames=0;
                if(++m_pose==3){Finish(tool);return;}
            }else if(now-m_waitStart>180) {
                tool.ReportAddRowValues({"pose",std::to_string(m_pose),vaStringTools::Format("%.1f",kPoses[m_pose]),"no shot marker","FAIL"});
                m_failed=true;Finish(tool);
            }
            return;
        }
        if(m_rendered){m_rendered=false;++m_frames;}
        if(m_frames>=90) {
            FILE *f=nullptr;
            if(_wfopen_s(&f,File(L"ready_",m_pose).c_str(),L"w")==0&&f){fprintf(f,"%d %.1f\n",m_pose,kPoses[m_pose]);fclose(f);}
            else {m_failed=true;Finish(tool);return;}
            m_waiting=true;m_waitStart=now;
        }
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext&,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;
        if(m_parent.Settings().CurrentAAOption!=CMAA2Sample::AAType::None){m_failed=true;tool.ReportAddRowValues({"failed_aa","FAIL"});}
        if(m_frames==0&&!m_waiting)tool.ReportAddRowValues({"pose_size",std::to_string(m_pose),std::to_string(color->GetSizeX()),std::to_string(color->GetSizeY())});
    }
    bool IsDone(AutoBenchTool&) const override {return m_done;}
    float GetProgress() const override {return float(m_pose)/3.0f;}
};

static void QueueReShadeStill(CMAA2Sample& parent,AutoBenchTool& tool) {
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()) {
        if(_wcsicmp(p.first.c_str(),L"smaaReShadeStillCapture")!=0)continue;
        std::wistringstream input(p.second);std::wstring scene,dir;input>>scene>>dir;
        if((scene!=L"bistro"&&scene!=L"minecraft")||dir.empty()){VA_LOG_ERROR("Expected scene and handshake directory without spaces");return;}
        tool.AddTask(std::make_shared<BenchItemReShadeStill>(parent,scene==L"minecraft",dir));return;
    }
}
