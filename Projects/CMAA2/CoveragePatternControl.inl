// Independent coverage-only quality gate. No performance claims from captures.
class BenchItemCoveragePattern : public AutoBenchToolWorkItem {
    struct Mode {const char *name;bool selectivePath,fullCoverage,pattern,diagnostics;};
    const std::vector<Mode> m_modes={
        {"ABL-Spatial-FirstEdge-Stencil-PatternOff-R",true,false,false,true},
        {"ABL-Spatial-FullScreen-PatternOff-R",true,true,false,true},
        {"O-T2X-R",false,false,true,false},
        {"ABL-Native-FullScreen-PatternOff-R",false,false,false,false},
        {"ABL-Spatial-FullScreen-PatternOff-R-Repeat",true,true,false,false}};
    bool m_minecraft,m_smoke,m_started=false,m_done=false,m_failed=false,m_rendered=false;
    int m_slot=0,m_frame=-60;
    double m_lastProgress=0;
    std::wstring m_output;
    void Configure(){
        auto s=m_parent.GetSMAA();const auto &c=m_modes[m_slot];
        s->CleanupTemporaryResources();
        m_parent.Settings().CurrentAAOption=CMAA2Sample::AAType::SMAA_T2x_Reprojected;
        s->SetTemporalModeEnabled(true);s->SetTemporalReprojectionEnabled(true);
        s->SetFirstEdgeStencilEnabled(true);s->SetStencilUpstreamControl(false);
        s->SetSpatialFirstEdgeEnabled(c.selectivePath);s->SetFullScreenCoverageControl(c.fullCoverage);
        s->SetTemporalSamplePatternEnabled(c.pattern);s->SetExecutionDiagnostics(c.diagnostics);
        s->ResetTemporalHistory();m_frame=-60;m_rendered=false;
        m_lastProgress=m_parent.GetApplication().GetTimeFromStart();
    }
    void Finish(AutoBenchTool &tool){
        m_parent.GetSMAA()->SetExecutionDiagnostics(false);
        m_parent.GetSMAA()->SetFullScreenCoverageControl(false);
        tool.ReportAddText(m_failed?"Aggregate: FAIL\r\n":"Aggregate: PASS\r\n");tool.ReportFinish();m_done=true;
        const_cast<vaApplicationBase&>(m_parent.GetApplication()).Quit();
    }
public:
    BenchItemCoveragePattern(CMAA2Sample &parent,bool minecraft,bool smoke,const std::wstring &output)
        :AutoBenchToolWorkItem(parent),m_minecraft(minecraft),m_smoke(smoke),m_output(output){}
    void Tick(AutoBenchTool &tool,float) override {
        const double now=m_parent.GetApplication().GetTimeFromStart();
        if(!m_started){
            m_started=true;m_parent.GetSMAA()->GetSettings().Preset=vaSMAAWrapper::PRESET_ULTRA;
            m_parent.Settings().SceneChoice=m_minecraft?CMAA2Sample::SceneSelectionType::MinecraftLostEmpire:CMAA2Sample::SceneSelectionType::LumberyardBistro;
            m_parent.SetRequireDeterminism(true);m_parent.SetFixedDeltaTime(1.0f/60.0f);
            m_parent.PostProcessTonemap()->Settings().AutoExposureAdaptationSpeed=std::numeric_limits<float>::infinity();
            vaUIManager::GetInstance().SetVisible(false);vaUIManager::GetInstance().SetConsoleVisible(false);
            auto &app=const_cast<vaApplicationBase&>(m_parent.GetApplication());app.SetVsync(false);app.SetFramerateLimit(0);
            tool.ReportStart();
            tool.ReportAddText("Coverage/sample-pattern control; direct base corrected case6 304f749.\r\nUltra; fixed60; still60/move120/still60; warmup60; camera/depth motion only.\r\n");
            tool.ReportAddText("Same selective shader/input/history, temporal stencil test Off for matched full control. Native full Off bridge and diagnostic-Off repeat. No timing result.\r\n");
            std::wstring report=tool.ReportGetDir();while(!report.empty()&&(report.back()==L'\\'||report.back()==L'/'))report.pop_back();
            m_output+=std::wstring(m_smoke?L"/smoke/":L"/capture/")+(m_minecraft?L"minecraft/":L"bistro/")+report.substr(report.find_last_of(L"\\/")+1)+L"/";
            tool.ReportAddRowValues({"capture_root",vaStringTools::SimpleNarrow(m_output)});
            Configure();
        }else{
            if(!m_rendered){if(now-m_lastProgress>90){m_failed=true;tool.ReportAddText("Render-readiness timeout.\r\n");Finish(tool);}return;}
            m_rendered=false;m_lastProgress=now;++m_frame;
            if(m_frame>=(m_smoke?6:240)){
                if(++m_slot==int(m_modes.size())){Finish(tool);return;}Configure();
            }
        }
        const int phase=m_frame<0?0:m_frame;
        if(m_frame==0)m_parent.GetSMAA()->ResetTemporalHistory();
        m_parent.GetFlythroughCameraController()->SetPlayTime(2.0f+float(vaMath::Clamp(phase-60,0,120))/60.0f);
    }
    void OnRender(AutoBenchTool&) override {}
    void OnRenderComparePoint(AutoBenchTool &tool,vaImageCompareTool&,vaRenderDeviceContext &ctx,
        const shared_ptr<vaTexture> &color,shared_ptr<vaPostProcess>&) override {
        if(m_done)return;m_rendered=true;auto s=m_parent.GetSMAA();const auto &c=m_modes[m_slot];
        const auto jitter=s->GetLastTemporalProjectionOffset();
        bool ok=s->GetTemporalModeEnabled()&&s->GetTemporalReprojectionEnabled()&&s->GetFirstEdgeStencilEnabled()
            && !s->GetStencilUpstreamControl()&&s->GetSpatialFirstEdgeEnabled()==c.selectivePath
            && s->GetFullScreenCoverageControl()==c.fullCoverage&&s->GetTemporalSamplePatternEnabled()==c.pattern
            && s->HasZeroSubsampleIndices()==!c.pattern
            && (c.pattern?(abs(jitter.x)==.25f&&abs(jitter.y)==.25f):(jitter.x==0&&jitter.y==0));
        m_failed=m_failed||!ok;if(m_frame<0)return;
        tool.ReportAddRowValues({"mode_check",c.name,std::to_string(m_frame),c.pattern?"PatternOn":"PatternOff",ok?"PASS":"FAIL"});
        const auto dir=m_output+vaStringTools::SimpleWiden(c.name)+L"/";vaFileTools::EnsureDirectoryExists(dir);
        const auto prefix=dir+vaStringTools::SimpleWiden(vaStringTools::Format("frame_%05d",m_frame));
        if(!color->SaveToPNGFile(ctx,prefix+L".png"))m_failed=true;
        if(m_frame>=1){
            uint64 hashes[3]={};const bool read=s->ReadCoverageInputHashes(ctx,hashes);m_failed=m_failed||!read;
            tool.ReportAddRowValues({"input_hashes",c.name,std::to_string(m_frame),std::to_string(hashes[0]),std::to_string(hashes[1]),std::to_string(hashes[2]),read?"PASS":"FAIL"});
        }
        if(c.diagnostics && (m_smoke || (m_frame>=60&&m_frame<220))){
            if(!s->SaveSpatialEdgeSnapshot(ctx,prefix,true,false)||!s->SaveExecutionCoverage(ctx,prefix+L"-coverage.dds"))m_failed=true;
            const bool query=s->ExecutionQueryOK();m_failed=m_failed||!query;
            tool.ReportAddRowValues({"execution",c.name,std::to_string(m_frame),std::to_string(s->GetResolveInvocations()),std::to_string(s->GetResolveSamples()),query?"PASS":"FAIL"});
        }
        if(!c.pattern && ((m_smoke&&m_frame==1)||m_frame==100||m_frame==179||m_frame==180||m_frame==190))
            if(!s->SaveCoverageInputProbe(ctx,prefix))m_failed=true;
    }
    bool IsDone(AutoBenchTool&) const override{return m_done;}
    float GetProgress() const override{return float(m_slot)/float(m_modes.size());}
};
static void QueueCoveragePatternControl(CMAA2Sample &parent,AutoBenchTool &tool){
    for(const auto &p:parent.GetApplication().GetCommandLineParameters()){
        const bool capture=_wcsicmp(p.first.c_str(),L"smaaCoveragePatternCapture")==0;
        const bool smoke=_wcsicmp(p.first.c_str(),L"smaaCoveragePatternSmoke")==0;
        if(!capture&&!smoke)continue;
        std::wistringstream input(p.second);std::wstring scene,output;input>>scene>>output;
        if((scene!=L"bistro"&&scene!=L"minecraft")||output.empty()){VA_LOG_ERROR("Expected scene and output without spaces");return;}
        tool.AddTask(std::make_shared<BenchItemCoveragePattern>(parent,scene==L"minecraft",smoke,output));return;
    }
}
