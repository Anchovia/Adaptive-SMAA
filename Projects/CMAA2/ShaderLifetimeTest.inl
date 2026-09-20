// CPU ownership regression using the real shader task manager; no AA timing claim.
class BenchItemShaderLifetime : public AutoBenchToolWorkItem
{
    struct ProbeState {
        std::mutex mutex;
        std::condition_variable cv;
        bool waiting=false, release=false, completed=false, destroyed=false, passed=true;
    };
    class ProbeShader final : public vaShader {
        ProbeState& m_probe;
    public:
        ProbeShader(const vaRenderingModuleParams& params,ProbeState& probe) : vaShader(params),m_probe(probe) { }
        ~ProbeShader() override {
            std::lock_guard<std::mutex> lock(m_probe.mutex);
            m_probe.passed=m_probe.passed && m_probe.completed;
            m_probe.destroyed=true;
        }
        void WaitFinishIfBackgroundCreateActive() override {
            { std::lock_guard<std::mutex> lock(m_probe.mutex); m_probe.waiting=true; }
            m_probe.cv.notify_all();
            vaShader::WaitFinishIfBackgroundCreateActive();
        }
        void Clear() override { }
        bool IsCreated() override { return false; }
    protected:
        void CreateShader() override {
            std::unique_lock<std::mutex> lock(m_probe.mutex);
            if(!m_probe.cv.wait_for(lock,std::chrono::seconds(5),[&]{return m_probe.release;})) m_probe.passed=false;
            m_probe.passed=m_probe.passed && !m_probe.destroyed;
            m_probe.completed=true;
        }
        void DestroyShader() override { }
    };
    bool m_done=false;
    template<typename T> bool CheckFactory(vaRenderDevice& device) {
        auto shader=VA_RENDERING_MODULE_CREATE_SHARED(T,device);
        vaAutoRMI<T> automatic(device);
        return shader!=nullptr && automatic.get()!=nullptr &&
            std::get_deleter<vaRenderingModuleDeleter>(shader)!=nullptr &&
            std::get_deleter<vaRenderingModuleDeleter>(automatic.get())!=nullptr;
    }
public:
    BenchItemShaderLifetime(CMAA2Sample& parent) : AutoBenchToolWorkItem(parent) { }
    void Tick(AutoBenchTool& tool,float) override {
        if(m_done) return;
        tool.ReportStart();
        tool.ReportAddText("Shader ownership lifetime regression; no performance claim\r\n");
        for(auto shader:vaShader::GetAllShaderList()) shader->WaitFinishIfBackgroundCreateActive();
        const size_t initialCount=vaShader::GetAllShaderList().size();
        bool pass=true;
        auto& device=m_parent.GetRenderDevice();
        const vaRenderingModuleParams params(device);
        for(int i=0;i<32;++i) {
            ProbeState state;
            auto probe=std::shared_ptr<ProbeShader>(new ProbeShader(params,state),vaRenderingModuleDeleter());
            probe->CreateShaderFromBuffer("probe","ps_5_0","probe",{},false);
            // Release pending work only after the owner joins, before any destructor starts.
            std::thread release([&]{
                std::unique_lock<std::mutex> lock(state.mutex);
                if(!state.cv.wait_for(lock,std::chrono::seconds(5),[&]{return state.waiting;})) state.passed=false;
                state.release=true;state.cv.notify_all();
            });
            probe.reset();release.join();
            const bool ok=state.passed && state.waiting && state.completed && state.destroyed;
            pass=pass && ok;
            tool.ReportAddRowValues({"pending-owner-release",std::to_string(i),ok?"PASS":"FAIL"});
        }
        const bool factories=CheckFactory<vaVertexShader>(device) && CheckFactory<vaPixelShader>(device) &&
            CheckFactory<vaComputeShader>(device) && CheckFactory<vaHullShader>(device) &&
            CheckFactory<vaDomainShader>(device) && CheckFactory<vaGeometryShader>(device);
        pass=pass && factories;
        tool.ReportAddRowValues({"six-stage-shared-and-auto-factories",factories?"PASS":"FAIL"});
        for(int i=0;i<32;++i) {
            auto shader=VA_RENDERING_MODULE_CREATE_SHARED(vaPixelShader,device);
            shader->CreateShaderFromBuffer("float4 main():SV_Target{return float4(1,0,0,1);}","ps_5_0","main",{{"LIFETIME_PROBE",std::to_string(i)}},false);
            if(i%2) {shader->WaitFinishIfBackgroundCreateActive();pass=pass && shader->IsCreated();shader->Reload();}
            shader.reset();
            { vaAutoRMI<vaComputeShader> cs(device);
              cs->CreateShaderFromBuffer("[numthreads(1,1,1)] void main() {}","cs_5_0","main",{{"LIFETIME_PROBE",std::to_string(i)}},false); }
        }
        const bool drained=vaShader::GetNumberOfCompilingShaders()==0 && vaShader::GetAllShaderList().size()==initialCount;
        pass=pass && drained;
        tool.ReportAddRowValues({"real-ps-cs-immediate-release-and-reload",drained?"PASS":"FAIL"});
        tool.ReportAddText(pass?"Aggregate: PASS\r\n":"Aggregate: FAIL\r\n");
        tool.ReportFinish();m_done=true;
    }
    bool IsDone(AutoBenchTool&) const override {return m_done;}
    void OnRender(AutoBenchTool&) override { }
    float GetProgress() const override {return m_done?1.0f:0.0f;}
};
