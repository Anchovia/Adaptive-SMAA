// Spatial-only comparison: original 1X vs identical shaders plus stencil clear.
class BenchItemOneXStencilClear : public AutoBenchToolWorkItem {
    struct Mode { const char *name; bool clear; };
    std::vector<Mode> m_modes;
    bool m_capture,m_minecraft,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    bool m_savedClear=false,m_savedStatistics=false;
    int m_slot=0,m_frame=-60,m_run=0,m_measureFrames=4800,m_repeats=6;
    double m_until=0,m_lastProgress=0,m_lastTick=0;
    vaSMAAWrapper::Preset m_savedPreset=vaSMAAWrapper::PRESET_HIGH;
    std::vector<double> m_smaa,m_wall;
    Mode Current() const {return m_modes[m_run%2?m_modes.size()-1-m_slot:m_slot];}
    void Configure(){
        auto s=m_parent.GetSMAA();m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::SMAA;
        s->SetTemporalModeEnabled(false);s->SetTemporalReprojectionEnabled(false);
        s->CleanupTemporaryResources(); // No stencil contents inherited across modes.
        s->SetOneXStencilClear(Current().clear);s->SetOneXStencilStatistics(m_capture);
        m_frame=m_capture?-60:-300;m_smaa.clear();m_wall.clear();m_rendered=false;
        m_lastProgress=m_parent.GetApplication().GetTimeFromStart();m_lastTick=m_lastProgress;
    }
    static double Time(const char* name){auto p=vaProfiler::GetInstancePtr();auto n=p?p->FindNode(name):nullptr;return n?n->GetFrameLastTotalTimeGPU()*1000.0:0;}
    void Summarize(AutoBenchTool& tool,const char* metric,std::vector<double> v){
        if(v.size()!=size_t(m_measureFrames)){m_failed=true;return;}
        double mean=0;for(double x:v)mean+=x;mean/=v.size();std::sort(v.begin(),v.end());
        double variance=0;for(double x:v)variance+=(x-mean)*(x-mean);variance/=v.size();
        const size_t tail=std::max(size_t(1),v.size()/100);double tailMean=0;
        for(size_t i=v.size()-tail;i<v.size();++i)tailMean+=v[i];tailMean/=tail;
        tool.ReportAddRowValues({"timing",Current().name,std::to_string(m_run),metric,std::to_string(v.size()),
            vaStringTools::Format("%.9f",mean),vaStringTools::Format("%.9f",v[(v.size()-1)/2]),
            vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.95)]),vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.99)]),
            vaStringTools::Format("%.9f",sqrt(variance)),vaStringTools::Format("%.9f",1000.0/tailMean)});
    }
    void Finish(AutoBenchTool& tool){
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
        auto s=m_parent.GetSMAA();s->GetSettings().Preset=m_savedPreset;
        s->SetOneXStencilClear(m_savedClear);s->SetOneXStencilStatistics(m_savedStatistics);
        m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemOneXStencilClear(CMAA2Sample& parent,bool capture,bool minecraft,bool smoke):AutoBenchToolWorkItem(parent),m_capture(capture),m_minecraft(minecraft){
        m_measureFrames=smoke?240:4800;m_repeats=smoke?1:6;
        m_modes={{"O-1X-LegacyStencil",false},{"O-1X-ClearStencil",true}};
        if(capture){m_modes.push_back({"O-1X-LegacyStencil-Repeat",false});m_modes.push_back({"O-1X-ClearStencil-Repeat",true});}
    }
    void Tick(AutoBenchTool& tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(!m_started){
            m_started=true;auto s=m_parent.GetSMAA();m_savedPreset=s->GetSettings().Preset;
            m_savedClear=s->GetOneXStencilClear();m_savedStatistics=s->GetOneXStencilStatistics();
            s->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();tool.ReportAddText("SMAA 1X stencil-clear-only experiment; baseline c51ca28. Core/shaders unchanged.\r\n");
            tool.ReportAddText(std::string("Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nUltra; temporal/reprojection/jitter Off; fixed60; still60/move120/still60.\r\n");
            tool.ReportAddText(m_capture?"Capture: four 240-frame sequences; spatial PSInvocations query On; no timing claim.\r\n":"Performance: PNG/query/readback Off; 30s precondition; 300 warmup; 4800 frames x 6 repeats (Smoke 240 x 1); alternating order. Clear included in SMAA scope.\r\n");
            tool.ReportAddText("timing columns: type,mode,run,metric,samples,mean_ms,median_ms,p95_ms,p99_ms,stddev_ms,slowest_one_percent_equivalent_fps\r\n");
            Configure();if(!m_capture)m_until=now+30;
        }else{
            if(m_until!=0){
                if(now<m_until){m_parent.GetFlythroughCameraController()->SetPlayTime(2);return;}
                m_until=0;Configure();
            }else{
                if(!m_rendered){if(now-m_lastProgress>90){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
                m_rendered=false;m_lastProgress=now;
                if(!m_capture&&m_frame>=0){double t=Time("SMAA");if(t>0)m_smaa.push_back(t);else m_failed=true;m_wall.push_back((now-m_lastTick)*1000.0);}
                ++m_frame;
                if(m_frame>=(m_capture?240:m_measureFrames)){
                    if(!m_capture){Summarize(tool,"SMAA",m_smaa);Summarize(tool,"WallFrame",m_wall);}
                    if(++m_slot==int(m_modes.size())){m_slot=0;++m_run;}
                    if(m_run==(m_capture?1:m_repeats)){Finish(tool);return;}Configure();
                }
            }
        }
        m_lastTick=now;const int phase=m_frame<0?0:m_frame%240;
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;const auto s=m_parent.GetSMAA();const auto c=Current();
        const bool ok=m_parent.Settings().CurrentAAOption==CMAA2Sample::AAType::SMAA&&!s->GetTemporalModeEnabled()&&!s->GetTemporalReprojectionEnabled()&&s->GetOneXStencilClear()==c.clear&&s->GetOneXStencilStatistics()==m_capture&&(!m_capture||s->GetOneXStencilStatisticsValid());
        m_failed=m_failed||!ok;if(!m_capture||m_frame<0)return;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),c.clear?"Clear":"Legacy","TemporalOff","NoR",ok?"PASS":"FAIL",std::to_string(s->GetOneXSpatialPSInvocations())});
        const auto dir=tool.ReportGetDir()+vaStringTools::SimpleWiden(c.name)+L"\\";vaFileTools::EnsureDirectoryExists(dir);
        if(!color->SaveToPNGFile(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d.png",m_frame))))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_slot)/float(m_modes.size());}
};
static void QueueOneXStencilClearVerification(CMAA2Sample& parent,AutoBenchTool& tool){
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()){
        const bool capture=_wcsicmp(p.first.c_str(),L"smaaOneXStencilClearCapture")==0;
        const bool performance=_wcsicmp(p.first.c_str(),L"smaaOneXStencilClearBenchmark")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaOneXStencilClearSmoke")==0;
        if(!capture&&!performance&&!smoke)continue;std::wistringstream input(p.second);std::wstring scene;input>>scene;
        if(scene!=L"bistro"&&scene!=L"minecraft"){VA_LOG_ERROR("Expected bistro or minecraft");return;}
        tool.AddTask(std::make_shared<BenchItemOneXStencilClear>(parent,capture,scene==L"minecraft",smoke));return;
    }
}
