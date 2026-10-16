#include <map>
#include <cmath>

// Paired output-preserving optimization harness for case 17 (same process, same
// timeline). Each candidate mode differs from the case-17 mode by exactly one
// default-off toggle that is applied only on the selected feedback route.
//   Capture:   RGB PNG for every frame of every mode (no diagnostics).
//   Smoke/Benchmark: GPU timing, PNG/query/readback/pass timers Off.
//   Profile:   diagnostic per-pass GPU timers On for every mode (not a speed claim).
class BenchItemColorBlendOptimization : public AutoBenchToolWorkItem {
public:
    enum class Phase {Capture, Profile, Smoke, Benchmark};
private:
    struct Mode {const char *name; bool selected; unsigned optimizations;};
    enum : unsigned {OPT_DEPTH_STENCIL_CLEAR=1u,OPT_NEIGHBORHOOD_NO_DEPTH=2u,OPT_PRESENT_HISTORY=4u};
    std::vector<Mode> m_modes;
    Phase m_phase;
    bool m_minecraft,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    int m_slot=0,m_frame=-60,m_run=0,m_measureFrames,m_repeats;
    double m_until=0,m_lastProgress=0,m_lastTick=0;
    std::wstring m_output;
    std::map<std::string,std::vector<double>> m_samples;
    bool Capturing() const {return m_phase==Phase::Capture;}
    Mode Current() const {return m_modes[m_run%2?m_modes.size()-1-m_slot:m_slot];}
    void Configure() {
        const auto c=Current();auto s=m_parent.GetSMAA();
        s->CleanupTemporaryResources();
        m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        s->SetTemporalModeEnabled(true);s->SetTemporalReprojectionEnabled(true);
        s->SetFirstEdgeStencilEnabled(true);s->SetSpatialFirstEdgeEnabled(c.selected);
        s->SetStencilUpstreamControl(false);s->SetTemporalSamplePatternEnabled(!c.selected);
        s->SetPreviousRawEdgesEnabled(c.selected);s->SetBilinearHistoryRGBEnabled(c.selected);
        s->SetResolvedRGBFeedbackEnabled(c.selected);
        s->SetCatmullRomHistoryRGBEnabled(c.selected);
        s->SetFixedHistoryWeight080Enabled(c.selected);s->SetSourceTemporalComponentEnabled(c.selected);
        s->SetExecutionDiagnostics(false);s->SetThinLineTracePrefix(L"");
        s->SetPassProfiling(m_phase==Phase::Profile);
        ApplyOptimizations(s,c);
        s->ResetTemporalHistory();m_frame=Capturing()?-60:-300;
        m_samples.clear();m_rendered=false;m_lastProgress=m_lastTick=m_parent.GetApplication().GetTimeFromStart();
    }
    // Candidate toggles; each is applied only by the selected feedback route in Draw().
    static void ApplyOptimizations(const shared_ptr<vaSMAAWrapper>& s,const Mode& c) {
        s->SetSelectedDepthStencilClear((c.optimizations&OPT_DEPTH_STENCIL_CLEAR)!=0);
        s->SetSelectedNeighborhoodWithoutDepth((c.optimizations&OPT_NEIGHBORHOOD_NO_DEPTH)!=0);
        s->SetSelectedPresentHistory((c.optimizations&OPT_PRESENT_HISTORY)!=0);
    }
    std::wstring Prefix() const {
        const auto dir=m_output+vaStringTools::SimpleWiden(Current().name)+L"/";
        vaFileTools::EnsureDirectoryExists(dir);
        return dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d",m_frame));
    }
    static double Time(const char *name) {
        auto p=vaProfiler::GetInstancePtr();auto n=p?p->FindNode(name):nullptr;
        return n?n->GetFrameLastTotalTimeGPU()*1000.0:0;
    }
    void Summarize(AutoBenchTool& tool,const std::string& metric,std::vector<double> v) {
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
    void Finish(AutoBenchTool& tool) {
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();
        m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemColorBlendOptimization(CMAA2Sample& parent,Phase phase,bool minecraft,std::wstring output):
        AutoBenchToolWorkItem(parent),m_phase(phase),m_minecraft(minecraft),
        m_measureFrames(phase==Phase::Smoke?240:phase==Phase::Profile?2400:4800),m_repeats(phase==Phase::Smoke?1:phase==Phase::Profile?3:6),m_output(output) {
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend",true,0});
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-DepthStencilClear",true,OPT_DEPTH_STENCIL_CLEAR});
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth",true,OPT_NEIGHBORHOOD_NO_DEPTH});
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-PresentHistory",true,OPT_PRESENT_HISTORY});
        // Integration of the individually beneficial candidates (O1 measured slower and is excluded).
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory",true,OPT_NEIGHBORHOOD_NO_DEPTH|OPT_PRESENT_HISTORY});
        m_modes.push_back({"O-T2X-R",false,0});
    }
    void Tick(AutoBenchTool& tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(!m_started) {
            m_started=true;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto& app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();
            tool.ReportAddRowValues({"presentation_timeline","240","60","120","60","60fps","2.0"});
            tool.ReportAddText("Case17 paired optimization harness: native case4, case17 and single-toggle case17 candidates; renderer configuration otherwise identical to EdgeSourceTemporalComponent.inl.\r\n");
            tool.ReportAddText(std::string("Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nUltra; fixed60; still60/move120/still60 from play time 2.0; native paired pattern On; case17 pattern Off; camera/depth reprojection only.\r\n");
            static const char *phases[]={"Capture: RGB PNG every frame; production shaders only; no diagnostics.\r\n",
                "Profile: diagnostic per-pass GPU timers On for every mode; 30s precondition; 300 warmup; 2400 frames x 3 alternating repeats. Not a speed result.\r\n",
                "Smoke: PNG/query/readback Off; 30s precondition; 300 warmup; 240 frames x 1.\r\n",
                "Benchmark: PNG/query/readback Off; 30s precondition; 300 warmup; 4800 frames x 6 alternating repeats. History reset at each 240-frame loop.\r\n"};
            tool.ReportAddText(phases[int(m_phase)]);
            tool.ReportAddText("timing columns: type,mode,run,metric,samples,mean_ms,median_ms,p95_ms,p99_ms,stddev_ms,slowest_one_percent_equivalent_fps\r\n");
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            static const wchar_t *dirs[]={L"/capture/",L"/profile/",L"/smoke/",L"/timing/"};
            m_output+=std::wstring(dirs[int(m_phase)])+std::wstring(m_minecraft?L"minecraft/":L"bistro/")+report.substr(report.find_last_of(L"\\/")+1)+L"/";
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});
            Configure();if(!Capturing())m_until=now+30;
        }else {
            if(m_until!=0) {
                if(now<m_until){m_parent.GetFlythroughCameraController()->SetPlayTime(2);return;}
                m_until=0;Configure();
            }else {
                if(!m_rendered){if(now-m_lastProgress>90){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
                m_rendered=false;m_lastProgress=now;
                if(!Capturing()&&m_frame>=0) {
                    for(const auto name:{"WholeFrame","SMAA","SR_CameraVelocity","SF_Spatial","SR_Resolve"}) {
                        const double t=Time(name);if(!std::isfinite(t)||t<=0)m_failed=true;
                        m_samples[name].push_back(t);
                    }
                    if(m_phase==Phase::Profile)for(const auto name:{"SP_Prepare","SP_Edge","SP_Weights","SP_Neighborhood"}) {
                        const double t=Time(name);if(!std::isfinite(t)||t<=0)m_failed=true;
                        m_samples[name].push_back(t);
                    }
                    m_samples["WallFrame"].push_back((now-m_lastTick)*1000.0);
                }
                ++m_frame;
                if(m_frame>=(Capturing()?240:m_measureFrames)) {
                    if(!Capturing())for(auto& kv:m_samples)Summarize(tool,kv.first,kv.second);
                    if(++m_slot==int(m_modes.size())){m_slot=0;++m_run;}
                    if(m_run==(Capturing()?1:m_repeats)){Finish(tool);return;}Configure();
                }
            }
        }
        const auto c=Current();auto s=m_parent.GetSMAA();
        m_lastTick=now;const int phase=m_frame<0?0:m_frame%240;
        if(m_frame>=0&&phase==0)s->ResetTemporalHistory();
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;const auto s=m_parent.GetSMAA();const auto c=Current();
        bool ok=m_parent.Settings().CurrentAAOption==CMAA2Sample::AAType::SMAA_T2x_Reprojected&&s->GetTemporalModeEnabled()&&s->GetTemporalReprojectionEnabled();
        ok=ok&&s->GetFirstEdgeStencilEnabled()&&s->GetSpatialFirstEdgeEnabled()==c.selected&&!s->GetStencilUpstreamControl()&&s->GetTemporalSamplePatternEnabled()==!c.selected;
        ok=ok&&s->GetPreviousRawEdgesEnabled()==c.selected&&s->GetBilinearHistoryRGBEnabled()==c.selected&&s->GetResolvedRGBFeedbackEnabled()==c.selected&&s->GetCatmullRomHistoryRGBEnabled()==c.selected&&s->GetFixedHistoryWeight080Enabled()==c.selected&&s->GetSourceTemporalComponentEnabled()==c.selected;
        ok=ok&&s->GetSelectedDepthStencilClear()==((c.optimizations&OPT_DEPTH_STENCIL_CLEAR)!=0);
        ok=ok&&s->GetSelectedNeighborhoodWithoutDepth()==((c.optimizations&OPT_NEIGHBORHOOD_NO_DEPTH)!=0);
        ok=ok&&s->GetSelectedPresentHistory()==((c.optimizations&OPT_PRESENT_HISTORY)!=0);
        ok=ok&&((s->GetPresentedOutputOverride()!=nullptr)==((c.optimizations&OPT_PRESENT_HISTORY)!=0));
        const auto jitter=s->GetLastTemporalProjectionOffset();ok=ok&&(c.selected?(jitter.x==0&&jitter.y==0):(abs(jitter.x)==.25f&&abs(jitter.y)==.25f));
        if(!ok)tool.ReportAddRowValues({"failed_state",c.name,std::to_string(m_frame),"FAIL"});
        m_failed=m_failed||!ok;if(!Capturing()||m_frame<0)return;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),vaStringTools::Format("%.6f",jitter.x),vaStringTools::Format("%.6f",jitter.y),ok?"PASS":"FAIL"});
        const auto dir=m_output+vaStringTools::SimpleWiden(c.name)+L"/";vaFileTools::EnsureDirectoryExists(dir);
        if(!color->SaveToPNGFile(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d.png",m_frame))))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override {return m_done;}
    float GetProgress() const override {return float(m_slot)/float(m_modes.size());}
};

static void QueueColorBlendOptimization(CMAA2Sample& parent,AutoBenchTool& tool) {
    using Phase=BenchItemColorBlendOptimization::Phase;
    static const std::pair<const wchar_t*,Phase> commands[]={
        {L"smaaColorBlendOptimizationCapture",Phase::Capture},{L"smaaColorBlendOptimizationProfile",Phase::Profile},
        {L"smaaColorBlendOptimizationSmoke",Phase::Smoke},{L"smaaColorBlendOptimizationBenchmark",Phase::Benchmark}};
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()) {
        for(const auto& command:commands) {
            if(_wcsicmp(p.first.c_str(),command.first)!=0)continue;
            std::wistringstream input(p.second);std::wstring scene,output;input>>scene>>output;
            if((scene!=L"bistro"&&scene!=L"minecraft")||output.empty()){VA_LOG_ERROR("Expected scene and output path without spaces");return;}
            tool.AddTask(std::make_shared<BenchItemColorBlendOptimization>(parent,command.second,scene==L"minecraft",output));return;
        }
    }
}
