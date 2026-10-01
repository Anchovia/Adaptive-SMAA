#include <map>
#include <cmath>
// Each branch supplies one target and the corrected native T2X-R control.
class BenchItemEdgePersistenceSpatialCost : public AutoBenchToolWorkItem {
    struct Mode {const char* name; CMAA2Sample::AAType type; bool target; int persistence; bool diagnostics;};
    std::vector<Mode> m_modes;
    bool m_shortCapture=false;
    bool m_profile=false;
    bool m_capture,m_minecraft,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    int m_slot=0,m_frame=-60,m_run=0,m_measureFrames=4800,m_repeats=3;
    double m_until=0,m_lastProgress=0,m_lastTick=0;
    std::wstring m_output;
    std::map<std::string,std::vector<double>> m_samples;
    Mode Current() const {return m_modes[m_run%2?m_modes.size()-1-m_slot:m_slot];}
    void Configure(){
        auto s=m_parent.GetSMAA();const auto c=Current();
        s->CleanupTemporaryResources();
        m_parent.Settings().CurrentAAOption=c.type;
        s->SetTemporalModeEnabled(c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected);
        s->SetTemporalReprojectionEnabled(c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected);
        s->SetSpatialPassProfiling(m_profile);s->SetEdgePersistenceMode(c.persistence);s->SetThinLineTracePrefix(L"");s->SetFirstEdgeStencilEnabled(true);s->SetExecutionDiagnostics(false);s->SetSpatialFirstEdgeEnabled(c.target);s->SetStencilUpstreamControl(false);s->SetTemporalSamplePatternEnabled(!c.target);
        s->ResetTemporalHistory();m_frame=m_capture?-60:-300;m_samples.clear();m_rendered=false;
        m_lastProgress=m_lastTick=m_parent.GetApplication().GetTimeFromStart();
    }
    bool TraceFrame() const {
        return m_frame>=0&&(m_shortCapture||m_frame<=1||m_frame==59||m_frame==60||m_frame==61||
            (m_frame>=126&&m_frame<=138)||(m_frame>=172&&m_frame<=195)||m_frame==239);
    }
    std::wstring Prefix() const {
        const auto dir=m_output+vaStringTools::SimpleWiden(Current().name)+L"/";
        vaFileTools::EnsureDirectoryExists(dir);
        return dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d",m_frame));
    }
    static double Time(const char* name){auto p=vaProfiler::GetInstancePtr();auto n=p?p->FindNode(name):nullptr;return n?n->GetFrameLastTotalTimeGPU()*1000.0:0;}
    void Summarize(AutoBenchTool& tool,const std::string& metric,std::vector<double> v){
        if(v.size()!=size_t(m_measureFrames)){m_failed=true;return;}
        double mean=0;for(double x:v)mean+=x;mean/=v.size();std::sort(v.begin(),v.end());
        double variance=0;for(double x:v)variance+=(x-mean)*(x-mean);variance/=v.size();
        const size_t tail=std::max(size_t(1),v.size()/100);double tailMean=0;
        for(size_t i=v.size()-tail;i<v.size();++i)tailMean+=v[i];tailMean/=tail;
        tool.ReportAddRowValues({"timing",Current().name,std::to_string(m_run),metric,std::to_string(v.size()),
            vaStringTools::Format("%.9f",mean),vaStringTools::Format("%.9f",v[(v.size()-1)/2]),
            vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.95)]),vaStringTools::Format("%.9f",v[size_t((v.size()-1)*.99)]),
            vaStringTools::Format("%.9f",sqrt(variance)),vaStringTools::Format("%.9f",tailMean>0?1000/tailMean:0)});
    }
    void Finish(AutoBenchTool& tool){
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
        m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemEdgePersistenceSpatialCost(CMAA2Sample& parent,bool capture,bool minecraft,bool smoke,std::wstring output,bool shortCapture=false,bool profile=false):AutoBenchToolWorkItem(parent),m_capture(capture),m_minecraft(minecraft),m_output(output){
        m_shortCapture=shortCapture;m_profile=profile;m_measureFrames=smoke?240:(profile?960:4800);m_repeats=smoke?1:3;
        const auto type=CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        m_modes={{"A-CurrentEdge-Stencil",type,true,0,true},
                 {"E-PreviousRawEdge-FirstStencil",type,true,7,true},
                 {"F-EagerPreviousFetch",type,true,8,true},
                 {"U-DepthMask-UnionWeights",type,true,9,true},
                 {"G-DepthMask-CurrentWeights",type,true,10,true},
                 {"O-T2X-R",type,false,0,false}};
    }
    void Tick(AutoBenchTool& tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(!m_started){
            m_started=true;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();
            tool.ReportAddText(std::string("Spatial pass profiling: ")+(m_profile?"On":"Off")+"\r\n");
            tool.ReportAddRowValues({"shader_stencil_reference_supported",m_parent.GetSMAA()->GetShaderStencilRefSupported()?"1":"0"});
            tool.ReportAddText("Spatial cost experiment. A=case6; E=case8; F=eager previous fetch; U=first-pass current depth export with union weights; G=same export with current-only weights; O=native4.\r\n");
            tool.ReportAddText(std::string("Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nUltra; fixed60; still60/move120/still60; camera/depth motion only.\r\n");
            tool.ReportAddText("Native pattern On; selective pattern Off. Spatial-frame history; no new filtering/dilation. Required stencil clears included in total SMAA GPU scope; AA-Off has zero AA work by definition.\r\n");
            tool.ReportAddText(m_capture?"Capture: six variants 240 frames each. Test: six frames each. F/U/G must match E; A/O must match preserved controls. Trace readbacks and queries only on explicit diagnostic frames; no timing claim.\r\n":"Timing: all six variants; PNG/query/readback Off; 30s precondition; 300 warmup; clean 4800 frames x 3, diagnostic Profile 960 x 3 (Smoke 240 x 1). Mode resources recreated; history reset at every 240-frame loop boundary.\r\n");
            tool.ReportAddText("timing columns: type,mode,run,metric,samples,mean_ms,median_ms,p95_ms,p99_ms,stddev_ms,slowest_one_percent_equivalent_fps\r\n");
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            m_output+=std::wstring(m_capture?(m_shortCapture?L"/test/":L"/capture/"):L"/timing/")+std::wstring(m_minecraft?L"minecraft/":L"bistro/")+report.substr(report.find_last_of(L"\\/")+1)+L"/";
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});
            Configure();if(!m_capture)m_until=now+30;
        }else{
            if(m_until!=0){
                if(now<m_until){m_parent.GetFlythroughCameraController()->SetPlayTime(2);return;}
                m_until=0;Configure();
            }else{
                if(!m_rendered){if(now-m_lastProgress>90){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
                m_rendered=false;m_lastProgress=now;
                if(!m_capture&&m_frame>=0){
                    const auto c=Current();
                    for(const auto name:{"WholeFrame","SMAA","SR_CameraVelocity","SF_Spatial","SR_Resolve","SP_Prepare","SP_Edge","SP_Weights","SP_Neighborhood"}){
                        if(std::string(name).substr(0,3)=="SP_"&&!m_profile)continue;
                        const bool aa=c.type!=CMAA2Sample::AAType::None;
                        const bool temporal=c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected;
                        if(std::string(name).substr(0,3)=="SR_"&&!temporal)continue;
                        const double t=std::string(name)=="SMAA"&&!aa?0:Time(name);
                        if(!std::isfinite(t)||(t<=0&&!(std::string(name)=="SMAA"&&!aa)))m_failed=true;
                        m_samples[name].push_back(t);
                    }
                    m_samples["WallFrame"].push_back((now-m_lastTick)*1000.0);
                }
                ++m_frame;
                if(m_frame>=(m_capture?(m_shortCapture?6:240):m_measureFrames)){
                    if(!m_capture)for(auto& kv:m_samples)Summarize(tool,kv.first,kv.second);
                    if(++m_slot==int(m_modes.size())){m_slot=0;++m_run;}
                    if(m_run==(m_capture?1:m_repeats)){Finish(tool);return;}Configure();
                }
            }
        }
        const auto c=Current();auto s=m_parent.GetSMAA();
        const bool diagnostic=m_capture&&c.diagnostics&&TraceFrame();
        s->SetExecutionDiagnostics(diagnostic);
        s->SetThinLineTracePrefix(diagnostic?Prefix():L"");
        m_lastTick=now;const int phase=m_frame<0?0:m_frame%240;
        if(m_frame>=0&&phase==0)m_parent.GetSMAA()->ResetTemporalHistory();
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;const auto s=m_parent.GetSMAA();const auto c=Current();
        const bool temporal=c.type==CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        bool ok=m_parent.Settings().CurrentAAOption==c.type&&s->GetTemporalModeEnabled()==temporal&&s->GetTemporalReprojectionEnabled()==temporal;
        ok=ok&&s->GetFirstEdgeStencilEnabled()&&s->GetSpatialFirstEdgeEnabled()==c.target&&!s->GetStencilUpstreamControl()&&s->GetTemporalSamplePatternEnabled()==!c.target&&s->GetEdgePersistenceMode()==c.persistence; const auto jitter=s->GetLastTemporalProjectionOffset();if(temporal)ok=ok&&(c.target?(jitter.x==0&&jitter.y==0):(abs(jitter.x)==.25f&&abs(jitter.y)==.25f));
        m_failed=m_failed||!ok;if(!m_capture||m_frame<0)return;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),temporal?"TemporalOn":"TemporalOff",ok?"PASS":"FAIL"});
        const auto dir=m_output+vaStringTools::SimpleWiden(c.name)+L"/";vaFileTools::EnsureDirectoryExists(dir);
        if(c.diagnostics&&TraceFrame()) {
            const auto prefix=Prefix();
            const bool inputs=s->SaveThinLineTraceInputs(ctx,prefix)&&s->SaveSpatialEdgeSnapshot(ctx,prefix,true,false);
            const bool coverage=s->SaveExecutionCoverage(ctx,prefix+L"-coverage.dds");
            const bool query=s->ExecutionQueryOK();m_failed=m_failed||!inputs||!coverage||!query;
            tool.ReportAddRowValues({"trace",c.name,std::to_string(m_frame),std::to_string(s->GetResolveInvocations()),std::to_string(s->GetResolveSamples()),inputs&&coverage&&query?"PASS":"FAIL",std::to_string(s->GetWeightSamples()),std::to_string(s->GetWeightInvocations())});
        }
        if(!color->SaveToPNGFile(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d.png",m_frame))))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_slot)/float(m_modes.size());}
};
static void QueueEdgePersistenceSpatialCost(CMAA2Sample& parent,AutoBenchTool& tool){
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()){
        const bool test=_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostTest")==0;
        const bool capture=test||_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostCapture")==0;
        const bool profile=_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostProfileBenchmark")==0||_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostProfileSmoke")==0;
        const bool benchmark=_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostBenchmark")==0||_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostProfileBenchmark")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostSmoke")==0||_wcsicmp(p.first.c_str(),L"smaaEdgePersistenceSpatialCostProfileSmoke")==0;
        if(!capture&&!benchmark&&!smoke)continue;std::wistringstream input(p.second);std::wstring scene,output;input>>scene>>output;
        if((scene!=L"bistro"&&scene!=L"minecraft")||output.empty()){VA_LOG_ERROR("Expected scene and output path without spaces");return;}
        tool.AddTask(std::make_shared<BenchItemEdgePersistenceSpatialCost>(parent,capture,scene==L"minecraft",smoke,output,test,profile));return;
    }
}
