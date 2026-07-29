///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Copyright (c) 2017, Intel Corporation
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of 
// the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
// THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
// TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
// SOFTWARE.
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//
// Author(s):  Filip Strugar (filip.strugar@intel.com)
//
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include "vaSMAAWrapper.h"

#include "IntegratedExternals/vaImguiIntegration.h"

using namespace VertexAsylum;

vaSMAAWrapper::vaSMAAWrapper( const vaRenderingModuleParams & params ) : vaRenderingModule( params ), vaUIPanel("SMAA", 0, false), m_constantsBuffer( params )
{ 
//    assert( vaRenderingCore::IsInitialized() );

    //m_debugShowEdges = false;
    memset( &m_constants, 0, sizeof(m_constants) );
}

vaSMAAWrapper::~vaSMAAWrapper( )
{
}

void vaSMAAWrapper::UIPanelDraw( )
{
#ifdef VA_IMGUI_INTEGRATION_ENABLED
    ImGui::PushItemWidth( 120.0f );


    ImGuiEx_Combo( "Quality preset", (int&)m_settings.Preset, { string("LOW"), string("MEDIUM"), string("HIGH"), string("ULTRA") } );

    if( GetEdgeSelectiveTemporalEnabled( ) )
    {
        ImGui::Separator( );
        ImGui::TextUnformatted( "TSCMAA candidate diagnostics" );

        bool policyOverrideEnabled = m_candidatePolicyOverrideEnabled;
        if( ImGui::Checkbox( "Override candidate policy", &policyOverrideEnabled ) )
            SetCandidatePolicyOverride( policyOverrideEnabled, m_candidatePolicyOverride );

        if( policyOverrideEnabled )
        {
            int policy = (int)m_candidatePolicyOverride;
            if( ImGuiEx_Combo( "Candidate policy", policy,
                { string("All base edges"), string("Intel-family non-dominant"), string("Experimental 3x3 mean/max") } ) )
                SetCandidatePolicyOverride( true, (CandidatePolicy)policy );
        }

        bool forcedCountEnabled = m_forcedCandidateCountEnabled;
        if( ImGui::Checkbox( "Force exact candidate count", &forcedCountEnabled ) )
            SetForcedCandidateCountForDiagnostics( forcedCountEnabled, m_forcedCandidateCount );
        if( forcedCountEnabled )
        {
            int forcedCount = (int)m_forcedCandidateCount;
            if( ImGui::InputInt( "Forced count", &forcedCount ) )
                SetForcedCandidateCountForDiagnostics( true, (uint32)vaMath::Max( forcedCount, 0 ) );
        }

        int debugView = (int)m_temporalDebugView;
        if( ImGuiEx_Combo( "Debug view", debugView, { string("Off"), string("Base edges"), string("Selected candidates") } ) )
            SetTemporalDebugView( (TemporalDebugView)debugView );

        const TemporalCandidateStatistics & statistics = GetTemporalCandidateStatistics( );
        if( statistics.Valid )
        {
            ImGui::Text( "Base edges: %u (%.3f%% of pixels)", statistics.BaseEdgeCount,
                statistics.PixelCount > 0? 100.0f * (float)statistics.BaseEdgeCount / (float)statistics.PixelCount : 0.0f );
            ImGui::Text( "Candidates: %u (%.3f%% of pixels)", statistics.CandidateCount,
                100.0f * statistics.GetCandidateToPixelRatio( ) );
            ImGui::Text( "Candidate/base: %.3f%%", 100.0f * statistics.GetCandidateToBaseRatio( ) );
            ImGui::Text( "Indirect processed: %u", statistics.ProcessCount );
            ImGui::Text( "Indirect groups: %u", statistics.DispatchGroupCount );
        }
        else
        {
            ImGui::TextDisabled( "Candidate counters are waiting for GPU readback." );
        }

        if( m_forcedCandidateCountEnabled )
        {
            const TemporalCandidateValidation & validation = GetTemporalCandidateValidation( );
            if( validation.Valid )
            {
                ImGui::TextColored( validation.Passed? ImVec4( 0.3f, 1.0f, 0.3f, 1.0f ) : ImVec4( 1.0f, 0.3f, 0.3f, 1.0f ),
                    "Boundary validation: %s", validation.Passed? "PASS" : "FAIL" );
                ImGui::Text( "Expected/read: %u / %u", validation.ExpectedCount, validation.ReadbackCount );
                ImGui::Text( "Duplicate/out-of-range/overflow: %u / %u / %u",
                    validation.DuplicateCount, validation.OutOfRangeCount, validation.CapacityOverflowCount );
            }
            else
            {
                ImGui::TextDisabled( "Candidate-list validation is waiting for GPU readback." );
            }
        }
    }

    ImGui::PopItemWidth();
#endif
}

// void vaSMAAWrapper::UpdateConstants( vaRenderDeviceContext & renderContext )
// {
//     apiContext;
// //    CMAA2ShaderConstants consts;
// //    consts.EdgeThreshold                    = m_settings.EdgeDetectionThreshold;
// //    consts.LocalContrastAdaptationAmount    = vaMath::Clamp( m_settings.LocalContrastAdaptationAmount, 0.0f, 0.5f );
// //    consts.SimpleShapeBlurrinessAmount      = m_settings.BlurinessAmount * 0.11f;
// //    consts.Unused                           = 0;
// //
// //    m_constantsBuffer.Update( apiContext, consts );
// }

