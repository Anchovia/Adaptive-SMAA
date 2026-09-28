// Independent temporal-only control. Baseline algorithms retained; original harness unchanged.
class BenchItemTemporalOnlyVerification : public AutoBenchToolWorkItem {
    struct Mode { const char* name; CMAA2Sample::AAType type; bool temporalOnly=false, reference=false; };
    std::vector<Mode> m_modes;
    bool m_capture,m_minecraft,m_started=false,m_done=false,m_failed=false;
    int m_slot=0,m_frame=-60,m_run=0,m_measureFrames=4800,m_repeats=4;
    double m_until=0;
    vaSMAAWrapper::Preset m_savedPreset=vaSMAAWrapper::PRESET_HIGH;
    std::vector<double> m_smaa;
    Mode Current() const {return m_modes[m_run%2?m_modes.size()-1-m_slot:m_slot];}
    void Configure(){m_parent.Settings().CurrentAAOption=Current().type;m_parent.GetSMAA()->SetTemporalOnlyControl(Current().temporalOnly,Current().reference);m_parent.GetSMAA()->ResetTemporalHistory();m_frame=m_capture?-60:-300;m_smaa.clear();}
    static double Time(const char* name){auto p=vaProfiler::GetInstancePtr();auto n=p?p->FindNode(name):nullptr;return n?n->GetFrameLastTotalTimeGPU()*1000.0:0;}
    void Summarize(AutoBenchTool& tool,const char* metric,std::vector<double> v){
        if(v.size()!=size_t(m_measureFrames)){m_failed=true;return;}double mean=0;for(double x:v)mean+=x;mean/=v.size();std::sort(v.begin(),v.end());
        tool.ReportAddRowValues({"timing",Current().name,std::to_string(m_run),metric,std::to_string(v.size()),vaStringTools::Format("%.9f",mean),vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.95)]),vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.99)])});
    }
public:
    BenchItemTemporalOnlyVerification(CMAA2Sample& parent,bool capture,bool minecraft,bool smoke=false):AutoBenchToolWorkItem(parent),m_capture(capture),m_minecraft(minecraft){
        m_measureFrames=smoke?240:4800;m_repeats=smoke?1:4;
        m_modes={{"O-1X",CMAA2Sample::AAType::SMAA},{"O-T2X-R",CMAA2Sample::AAType::SMAA_T2x_Reprojected},{"ABL-TemporalOnly-R",CMAA2Sample::AAType::SMAA_T2x_Reprojected,true,false}};
        if(capture){m_modes.insert(m_modes.begin(),{"AA-Off",CMAA2Sample::AAType::None});m_modes.push_back({"ABL-TemporalOnly-R-Repeat",CMAA2Sample::AAType::SMAA_T2x_Reprojected,true,false});m_modes.push_back({"REF-Native-ZeroWeights-R",CMAA2Sample::AAType::SMAA_T2x_Reprojected,true,true});}
    }
    void Tick(AutoBenchTool& tool,float) override {
        if(!m_started){
            m_started=true;m_savedPreset=m_parent.GetSMAA()->GetSettings().Preset;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();tool.ReportAddText("Temporal-only control from verified baseline e14f122. No spatial edge/weight/blend passes in ABL; raw RGB plus native velocity-alpha packing; unchanged native resolve. REF uses native neighborhood shader with zero weights, excluded from timings.\r\n");
            tool.ReportAddText(m_capture?"Purpose: 240-frame quality capture; no timing claim. AA-Off is unjittered no-AA; O-1X is actual spatial-only SMAA.\r\n":"Purpose: separate performance capture, 30s precondition; 300 warmup; 4800 frames x 4 repeats (Smoke 240 x 1); no PNG. SMAA scope only.\r\n");
            tool.ReportAddText(std::string("Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nUltra; fixed 60 Hz; flythrough t=2 + clamp(frame-60,0,120)/60; still60/move120/still60. Camera-only reprojection.\r\n");
            Configure();if(!m_capture)m_until=app.GetTimeFromStart()+30;
        }else{
            if(m_until!=0){if(m_parent.GetApplication().GetTimeFromStart()<m_until){m_parent.GetFlythroughCameraController()->SetPlayTime(2);return;}m_until=0;Configure();}
            else{
                if(!m_capture&&m_frame>=0){double s=Time("SMAA");if(s>0){m_smaa.push_back(s);}else m_failed=true;}
                ++m_frame;if(m_frame>=(m_capture?240:m_measureFrames)){
                    if(!m_capture){Summarize(tool,"SMAA",m_smaa);}
                    if(++m_slot==int(m_modes.size())){m_slot=0;++m_run;}
                    if(m_run==(m_capture?1:m_repeats)){tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();m_parent.GetSMAA()->GetSettings().Preset=m_savedPreset;m_parent.GetSMAA()->SetTemporalOnlyControl(false);m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();return;}Configure();
                }
            }
        }
        if(m_frame==0)m_parent.GetSMAA()->ResetTemporalHistory();const int phase=m_frame<0?0:m_frame%240;
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(!m_capture||m_frame<0||m_done)return;const auto c=Current();const auto s=m_parent.GetSMAA();
        const bool temporal=c.type==CMAA2Sample::AAType::SMAA_T2x||c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        const bool reprojection=c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        const bool ok=s->GetTemporalModeEnabled()==temporal&&s->GetTemporalReprojectionEnabled()==reprojection&&s->GetTemporalOnlyControl()==c.temporalOnly&&s->GetTemporalOnlyReference()==c.reference;m_failed=m_failed||!ok;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),temporal?"TemporalOn":"TemporalOff",reprojection?"CameraR":"NoR",ok?"PASS":"FAIL"});
        const auto dir=tool.ReportGetDir()+vaStringTools::SimpleWiden(c.name)+L"\\";vaFileTools::EnsureDirectoryExists(dir);
        if(c.temporalOnly && (m_frame==0||m_frame==1||m_frame==59||m_frame==60||m_frame==61||m_frame==100||m_frame==179||m_frame==180||m_frame==181||m_frame==239))
            if(!s->SaveTemporalOnlyInputs(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d",m_frame))))m_failed=true;
        if(!color->SaveToPNGFile(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d.png",m_frame))))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_slot)/float(m_modes.size());}
};
static void QueueTemporalOnlyVerification(CMAA2Sample& parent,AutoBenchTool& tool){
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()){
        const bool capture=_wcsicmp(p.first.c_str(),L"smaaTemporalOnlyCapture")==0;
        const bool performance=_wcsicmp(p.first.c_str(),L"smaaTemporalOnlyBenchmark")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaTemporalOnlySmoke")==0;
        if(!capture&&!performance&&!smoke)continue;std::wistringstream input(p.second);std::wstring scene;input>>scene;
        if(scene!=L"bistro"&&scene!=L"minecraft"){VA_LOG_ERROR("Expected bistro or minecraft");return;}
        tool.AddTask(std::make_shared<BenchItemTemporalOnlyVerification>(parent,capture,scene==L"minecraft",smoke));return;
    }
}
