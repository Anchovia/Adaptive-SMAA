#include <map>
#include <cmath>

// Case13 single hypothesis: normalized 5-tap RGB reconstruction; case11 feedback and point alpha remain fixed.
class BenchItemEdgeCatmullRomRGBFeedback : public AutoBenchToolWorkItem {
    struct Mode {const char *name; bool selected, previousRaw, bilinearRGB, feedback, catmull;};
    std::vector<Mode> m_modes;
    bool m_capture,m_minecraft,m_test,m_smoke,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    int m_slot=0,m_frame=-60,m_run=0,m_measureFrames,m_repeats;
    int m_captureFrames=240; float m_startTime=2.0f;
    double m_until=0,m_lastProgress=0,m_lastTick=0;
    std::wstring m_output;
    std::map<std::string,std::vector<double>> m_samples;
    Mode Current() const {return m_modes[m_run%2?m_modes.size()-1-m_slot:m_slot];}
    void Configure() {
        const auto c=Current();auto s=m_parent.GetSMAA();
        s->CleanupTemporaryResources();
        m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        s->SetTemporalModeEnabled(true);s->SetTemporalReprojectionEnabled(true);
        s->SetFirstEdgeStencilEnabled(true);s->SetSpatialFirstEdgeEnabled(c.selected);
        s->SetStencilUpstreamControl(false);s->SetTemporalSamplePatternEnabled(!c.selected);
        s->SetPreviousRawEdgesEnabled(c.previousRaw);s->SetBilinearHistoryRGBEnabled(c.bilinearRGB);
        s->SetResolvedRGBFeedbackEnabled(c.feedback);
        s->SetCatmullRomHistoryRGBEnabled(c.catmull);
        s->SetExecutionDiagnostics(false);s->SetThinLineTracePrefix(L"");
        s->ResetTemporalHistory();m_frame=m_capture?-60:-300;
        m_samples.clear();m_rendered=false;m_lastProgress=m_lastTick=m_parent.GetApplication().GetTimeFromStart();
    }
    bool TraceFrame() const {
        return m_frame>=0&&(m_test||m_frame<=1||m_frame==59||m_frame==60||m_frame==61||
            (m_frame>=126&&m_frame<=138)||(m_frame>=172&&m_frame<=195)||m_frame==239);
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
    BenchItemEdgeCatmullRomRGBFeedback(CMAA2Sample& parent,bool capture,bool minecraft,bool smoke,std::wstring output,bool test,int frames=240,float start=2.0f):
        AutoBenchToolWorkItem(parent),m_capture(capture),m_minecraft(minecraft),m_test(test),m_smoke(smoke),
        m_measureFrames(smoke?240:4800),m_repeats(smoke?1:6),m_output(output) {
        m_captureFrames=frames;m_startTime=start;
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-BilinearRGB",true,true,true,false,false});
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-ResolvedRGB",true,true,true,true,false});
        m_modes.push_back({"ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB",true,true,true,true,true});
        m_modes.push_back({"O-T2X-R",false,false,false,false,false});
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
            tool.ReportAddRowValues({"presentation_timeline",std::to_string(m_capture?m_captureFrames:240),"60",std::to_string(m_capture?m_captureFrames-120:120),"60","60fps",std::to_string(m_capture?m_startTime:2.0f)});
            tool.ReportAddText("Case13 history RGB filter experiment. Original spatial SMAA; camera/depth reprojection only.\r\n");
            tool.ReportAddText(std::string("Scene: ")+(m_minecraft?"minecraft":"bistro")+"\r\nUltra; fixed60; timeline from presentation_timeline; native paired pattern On; selected pattern Off.\r\n");
            tool.ReportAddText("Point velocity alpha, native adaptive 0..0.5 weight, raw-edge union and nonselected current output are fixed. Case10 spatial-frame bilinear RGB; case11 resolved bilinear RGB; case13 resolved normalized 5-tap Catmull-Rom RGB. No dilation, clipping, weight change or extra draw/copy/texture beyond case11.\r\n");
            tool.ReportAddText(m_capture?"Capture: case10, case11, case13 and native4; default240 frames (Test6; reset again at frame3). Selected trace frames save raw/current/previous/velocity/edge/coverage/R32 weight. No timing claim.\r\n":"Timing: case10, case11, case13 and native4; PNG/query/readback Off; 30s precondition; 300 warmup; 4800 frames x 6 alternating repeats (Smoke240 x1). History reset at each 240-frame loop.\r\n");
            tool.ReportAddText("timing columns: type,mode,run,metric,samples,mean_ms,median_ms,p95_ms,p99_ms,stddev_ms,slowest_one_percent_equivalent_fps\r\n");
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            m_output+=std::wstring(m_capture?(m_test?L"/test/":L"/capture/"):L"/timing/")+std::wstring(m_minecraft?L"minecraft/":L"bistro/")+report.substr(report.find_last_of(L"\\/")+1)+L"/";
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});
            Configure();if(!m_capture)m_until=now+30;
        }else {
            if(m_until!=0) {
                if(now<m_until){m_parent.GetFlythroughCameraController()->SetPlayTime(2);return;}
                m_until=0;Configure();
            }else {
                if(!m_rendered){if(now-m_lastProgress>90){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
                m_rendered=false;m_lastProgress=now;
                if(!m_capture&&m_frame>=0) {
                    for(const auto name:{"WholeFrame","SMAA","SR_CameraVelocity","SF_Spatial","SR_Resolve"}) {
                        const double t=Time(name);if(!std::isfinite(t)||t<=0)m_failed=true;
                        m_samples[name].push_back(t);
                    }
                    m_samples["WallFrame"].push_back((now-m_lastTick)*1000.0);
                }
                ++m_frame;
                if(m_frame>=(m_capture?(m_test?6:m_captureFrames):m_measureFrames)) {
                    if(!m_capture)for(auto& kv:m_samples)Summarize(tool,kv.first,kv.second);
                    if(++m_slot==int(m_modes.size())){m_slot=0;++m_run;}
                    if(m_run==(m_capture?1:m_repeats)){Finish(tool);return;}Configure();
                }
            }
        }
        const auto c=Current();auto s=m_parent.GetSMAA();
        const bool diagnostic=m_capture&&m_captureFrames==240&&c.selected&&TraceFrame();
        s->SetExecutionDiagnostics(diagnostic);s->SetThinLineTracePrefix(diagnostic?Prefix():L"");
        m_lastTick=now;const int phase=m_frame<0?0:m_frame%(m_capture?m_captureFrames:240);
        if(m_frame>=0&&(phase==0||(m_test&&m_frame==3)))s->ResetTemporalHistory();
        m_parent.GetFlythroughCameraController()->SetPlayTime((m_capture?m_startTime:2.0f)+float(vaMath::Clamp(phase-60,0,m_capture?m_captureFrames-120:120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool& tool,vaImageCompareTool&,vaRenderDeviceContext& ctx,const shared_ptr<vaTexture>& color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;const auto s=m_parent.GetSMAA();const auto c=Current();
        bool ok=m_parent.Settings().CurrentAAOption==CMAA2Sample::AAType::SMAA_T2x_Reprojected&&s->GetTemporalModeEnabled()&&s->GetTemporalReprojectionEnabled();
        ok=ok&&s->GetFirstEdgeStencilEnabled()&&s->GetSpatialFirstEdgeEnabled()==c.selected&&!s->GetStencilUpstreamControl()&&s->GetTemporalSamplePatternEnabled()==!c.selected;
        ok=ok&&s->GetPreviousRawEdgesEnabled()==c.previousRaw&&s->GetBilinearHistoryRGBEnabled()==c.bilinearRGB&&s->GetResolvedRGBFeedbackEnabled()==c.feedback&&s->GetCatmullRomHistoryRGBEnabled()==c.catmull;
        const auto jitter=s->GetLastTemporalProjectionOffset();ok=ok&&(c.selected?(jitter.x==0&&jitter.y==0):(abs(jitter.x)==.25f&&abs(jitter.y)==.25f));
        if(!ok)tool.ReportAddRowValues({"failed_state",c.name,std::to_string(m_frame),
            std::to_string(int(m_parent.Settings().CurrentAAOption)),
            std::to_string(s->GetTemporalModeEnabled()),std::to_string(s->GetTemporalReprojectionEnabled()),
            std::to_string(s->GetFirstEdgeStencilEnabled()),std::to_string(s->GetSpatialFirstEdgeEnabled()),
            std::to_string(s->GetStencilUpstreamControl()),std::to_string(s->GetTemporalSamplePatternEnabled()),
            std::to_string(s->GetPreviousRawEdgesEnabled()),std::to_string(s->GetBilinearHistoryRGBEnabled()),
            std::to_string(s->GetResolvedRGBFeedbackEnabled()),
            vaStringTools::Format("%.6f",jitter.x),vaStringTools::Format("%.6f",jitter.y),"FAIL"});
        m_failed=m_failed||!ok;if(!m_capture||m_frame<0)return;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),"TemporalOn",ok?"PASS":"FAIL"});
        if(m_captureFrames==240&&c.selected&&TraceFrame()) {
            const auto prefix=Prefix();
            const bool inputs=s->SaveThinLineTraceInputs(ctx,prefix)&&s->SaveSpatialEdgeSnapshot(ctx,prefix,true,false);
            const bool coverage=s->SaveExecutionCoverage(ctx,prefix+L"-coverage.dds");
            const bool weight=s->SaveHistoryWeightDiagnostic(ctx,prefix+L"-weight.dds");
            const bool history=s->SaveResolvedHistoryDiagnostic(ctx,prefix+L"-next-history.dds");
            const bool query=s->ExecutionQueryOK();m_failed=m_failed||!inputs||!coverage||!weight||!query||!history;
            tool.ReportAddRowValues({"trace",c.name,std::to_string(m_frame),std::to_string(s->GetResolveInvocations()),std::to_string(s->GetResolveSamples()),inputs&&coverage&&weight&&query&&history?"PASS":"FAIL"});
        }
        const auto dir=m_output+vaStringTools::SimpleWiden(c.name)+L"/";vaFileTools::EnsureDirectoryExists(dir);
        if(!color->SaveToPNGFile(ctx,dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d.png",m_frame))))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override {return m_done;}
    float GetProgress() const override {return float(m_slot)/float(m_modes.size());}
};

static void QueueEdgeCatmullRomRGBFeedback(CMAA2Sample& parent,AutoBenchTool& tool) {
    for(const auto& p:parent.GetApplication().GetCommandLineParameters()) {
        const bool test=_wcsicmp(p.first.c_str(),L"smaaEdgeCatmullRomRGBFeedbackTest")==0;
        const bool capture=test||_wcsicmp(p.first.c_str(),L"smaaEdgeCatmullRomRGBFeedbackCapture")==0;
        const bool benchmark=_wcsicmp(p.first.c_str(),L"smaaEdgeCatmullRomRGBFeedbackBenchmark")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaEdgeCatmullRomRGBFeedbackSmoke")==0;
        if(!capture&&!benchmark&&!smoke)continue;
        std::wistringstream input(p.second);std::wstring scene,output;input>>scene>>output;int frames=240;float start=2.0f;input>>frames>>start;
        if(frames<240||frames>1440||!std::isfinite(start)||start<0){VA_LOG_ERROR("Invalid capture timeline");return;}
        if((scene!=L"bistro"&&scene!=L"minecraft")||output.empty()){VA_LOG_ERROR("Expected scene and output path without spaces");return;}
        tool.AddTask(std::make_shared<BenchItemEdgeCatmullRomRGBFeedback>(parent,capture,scene==L"minecraft",smoke,output,test,frames,start));return;
    }
}
