// Capture-only input trace. Production SMAA shaders and resolve are unchanged.
class BenchItemThinLineTrace : public AutoBenchToolWorkItem {
    struct Mode { const char *name; bool selective, diagnostics; };
    const std::vector<Mode> m_modes={
        {"ABL-Spatial-FirstEdge-Stencil-PatternOff-R",true,true},
        {"O-T2X-R",false,true},
        {"ABL-Spatial-FirstEdge-Stencil-PatternOff-R-Repeat",true,false}};
    bool m_minecraft,m_smoke,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    int m_slot=0,m_frame=-60;
    double m_lastProgress=0;
    std::wstring m_output;
    bool IsTraceFrame() const {
        return m_smoke ? m_frame>=1 :
            ((m_frame>=127&&m_frame<=138)||(m_frame>=173&&m_frame<=185)||(m_frame>=189&&m_frame<=195));
    }
    std::wstring Prefix() const {
        return m_output+vaStringTools::SimpleWiden(m_modes[m_slot].name)+L"/"
            +vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d",m_frame));
    }
    void Configure() {
        auto s=m_parent.GetSMAA();const auto c=m_modes[m_slot];
        s->SetThinLineTracePrefix(L"");s->CleanupTemporaryResources();
        m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        s->SetTemporalModeEnabled(true);s->SetTemporalReprojectionEnabled(true);
        s->SetFirstEdgeStencilEnabled(true);s->SetStencilUpstreamControl(false);
        s->SetSpatialFirstEdgeEnabled(c.selective);s->SetTemporalSamplePatternEnabled(!c.selective);
        s->SetExecutionDiagnostics(false);s->ResetTemporalHistory();m_frame=-60;m_rendered=false;
        vaFileTools::EnsureDirectoryExists(m_output+vaStringTools::SimpleWiden(c.name)+L"/");
        m_lastProgress=m_parent.GetApplication().GetTimeFromStart();
    }
    void Finish(AutoBenchTool &tool) {
        m_parent.GetSMAA()->SetThinLineTracePrefix(L"");m_parent.GetSMAA()->SetExecutionDiagnostics(false);
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");
        tool.ReportFinish();m_done=true;const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemThinLineTrace(CMAA2Sample &p,bool minecraft,bool smoke,const std::wstring &output)
        :AutoBenchToolWorkItem(p),m_minecraft(minecraft),m_smoke(smoke),m_output(output){}
    void Tick(AutoBenchTool &tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(!m_started) {
            m_started=true;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto &app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();tool.ReportAddText("Thin-line input trace; direct base 304f749; no shader math change.\r\nUltra; fixed60; still60/move120/still60; warmup60; camera/depth reprojection; no timing claim.\r\n");
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            m_output+=std::wstring(m_smoke?L"/smoke/":L"/capture/")+(m_minecraft?L"minecraft/":L"bistro/")+report.substr(report.find_last_of(L"\\/")+1)+L"/";
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});Configure();
        } else {
            if(!m_rendered) {if(now-m_lastProgress>90){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
            m_rendered=false;m_lastProgress=now;++m_frame;
            if(m_frame>=(m_smoke?6:240)) {if(++m_slot==int(m_modes.size())){Finish(tool);return;}Configure();}
        }
        auto s=m_parent.GetSMAA();const auto c=m_modes[m_slot];
        const bool trace=c.diagnostics&&IsTraceFrame();
        s->SetThinLineTracePrefix(trace?Prefix():L"");s->SetExecutionDiagnostics(trace);
        if(m_frame==0)s->ResetTemporalHistory();
        const int phase=m_frame<0?0:m_frame;
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool &tool,vaImageCompareTool&,vaRenderDeviceContext &ctx,
        const shared_ptr<vaTexture> &color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;auto s=m_parent.GetSMAA();const auto c=m_modes[m_slot];
        const auto j=s->GetLastTemporalProjectionOffset();
        const bool ok=s->GetTemporalModeEnabled()&&s->GetTemporalReprojectionEnabled()
            &&s->GetFirstEdgeStencilEnabled()&&!s->GetStencilUpstreamControl()
            &&s->GetSpatialFirstEdgeEnabled()==c.selective&&s->GetTemporalSamplePatternEnabled()==!c.selective
            &&s->HasZeroSubsampleIndices()==c.selective
            &&(c.selective?(j.x==0&&j.y==0):(abs(j.x)==.25f&&abs(j.y)==.25f));
        m_failed=m_failed||!ok;if(m_frame<0)return;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),c.selective?"PatternOff":"PatternOn",ok?"PASS":"FAIL"});
        const auto prefix=Prefix();if(!color->SaveToPNGFile(ctx,prefix+L".png"))m_failed=true;
        if(c.diagnostics&&IsTraceFrame()) {
            const bool inputs=s->SaveThinLineTraceInputs(ctx,prefix)&&s->SaveSpatialEdgeSnapshot(ctx,prefix,true,false);
            const bool cov=!c.selective||s->SaveExecutionCoverage(ctx,prefix+L"-coverage.dds");
            const bool query=s->ExecutionQueryOK();m_failed=m_failed||!inputs||!cov||!query;
            tool.ReportAddRowValues({"trace",c.name,std::to_string(m_frame),std::to_string(s->GetResolveInvocations()),
                std::to_string(s->GetResolveSamples()),inputs&&cov&&query?"PASS":"FAIL"});
        }
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_slot)/float(m_modes.size());}
};
static void QueueThinLineTrace(CMAA2Sample &parent,AutoBenchTool &tool) {
    for(const auto &p:parent.GetApplication().GetCommandLineParameters()) {
        const bool capture=_wcsicmp(p.first.c_str(),L"smaaThinLineTraceCapture")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaThinLineTraceSmoke")==0;
        if(!capture&&!smoke)continue;
        std::wistringstream input(p.second);std::wstring scene,output;input>>scene>>output;
        if((scene!=L"bistro"&&scene!=L"minecraft")||output.empty()){VA_LOG_ERROR("Expected scene and output without spaces");return;}
        tool.AddTask(std::make_shared<BenchItemThinLineTrace>(parent,scene==L"minecraft",smoke,output));return;
    }
}
