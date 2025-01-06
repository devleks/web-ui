# -*- coding: utf-8 -*-
# @Time    : 2025/1/1
# @Author  : wenshao
# @Email   : wenshaoguo1026@gmail.com
# @Project : browser-use-webui
# @FileName: webui.py
import pdb

from dotenv import load_dotenv

load_dotenv()
import argparse

import asyncio

import gradio as gr
import asyncio
import os
from pprint import pprint
from typing import List, Dict, Any

from playwright.async_api import async_playwright
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import (
    BrowserContext,
    BrowserContextConfig,
    BrowserContextWindowSize,
)
from browser_use.agent.service import Agent

from src.browser.custom_browser import CustomBrowser, BrowserConfig
from src.browser.custom_context import BrowserContext, BrowserContextConfig
from src.controller.custom_controller import CustomController
from src.agent.custom_agent import CustomAgent
from src.agent.custom_prompts import CustomSystemPrompt

from src.utils import utils

async def run_browser_agent(
        agent_type,
        llm_provider,
        llm_model_name,
        llm_temperature,
        llm_base_url,
        llm_api_key,
        use_own_browser,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        task,
        add_infos,
        max_steps,
        use_vision
):


    llm = utils.get_llm_model(
        provider=llm_provider,
        model_name=llm_model_name,
        temperature=llm_temperature,
        base_url=llm_base_url,
        api_key=llm_api_key
    )
    if agent_type == "org":
        return await run_org_agent(
            llm=llm,
            headless=headless,
            disable_security=disable_security,
            window_w=window_w,
            window_h=window_h,
            save_recording_path=save_recording_path,
            task=task,
            max_steps=max_steps,
            use_vision=use_vision
        )
    elif agent_type == "custom":
        return await run_custom_agent(
            llm=llm,
            use_own_browser=use_own_browser,
            headless=headless,
            disable_security=disable_security,
            window_w=window_w,
            window_h=window_h,
            save_recording_path=save_recording_path,
            task=task,
            add_infos=add_infos,
            max_steps=max_steps,
            use_vision=use_vision
        )
    else:
        raise ValueError(f"Invalid agent type: {agent_type}")

async def run_org_agent(
        llm,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        task,
        max_steps,
        use_vision
):
    browser = Browser(
        config=BrowserConfig(
            headless=headless,
            disable_security=disable_security,
            extra_chromium_args=[f'--window-size={window_w},{window_h}'],
        )
    )
    async with await browser.new_context(
            config=BrowserContextConfig(
                trace_path='./tmp/traces',
                save_recording_path=save_recording_path if save_recording_path else None,
                no_viewport=False,
                browser_window_size=BrowserContextWindowSize(width=window_w, height=window_h),
            )
    ) as browser_context:
        agent = Agent(
            task=task,
            llm=llm,
            use_vision=use_vision,
            browser_context=browser_context,
        )
        history = await agent.run(max_steps=max_steps)

        final_result = history.final_result()
        errors = history.errors()
        model_actions = history.model_actions()
        model_thoughts = history.model_thoughts()
    await browser.close()
    return final_result, errors, model_actions, model_thoughts

async def run_custom_agent(
        llm,
        use_own_browser,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        task,
        add_infos,
        max_steps,
        use_vision
):
    controller = CustomController()
    playwright = None
    browser_context_ = None
    try:
        if use_own_browser:
            playwright = await async_playwright().start()
            chrome_exe = os.getenv("CHROME_PATH", "")
            chrome_use_data = os.getenv("CHROME_USER_DATA", "")
            browser_context_ = await playwright.chromium.launch_persistent_context(
                user_data_dir=chrome_use_data,
                executable_path=chrome_exe,
                no_viewport=False,
                headless=headless,  # 保持浏览器窗口可见
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
                ),
                java_script_enabled=True,
                bypass_csp=disable_security,
                ignore_https_errors=disable_security,
                record_video_dir=save_recording_path if save_recording_path else None,
                record_video_size={'width': window_w, 'height': window_h}
            )
        else:
            browser_context_ = None

        browser = CustomBrowser(
            config=BrowserConfig(
                headless=headless,
                disable_security=disable_security,
                extra_chromium_args=[f'--window-size={window_w},{window_h}'],
            )
        )
        async with await browser.new_context(
                config=BrowserContextConfig(
                    trace_path='./tmp/result_processing',
                    save_recording_path=save_recording_path if save_recording_path else None,
                    no_viewport=False,
                    browser_window_size=BrowserContextWindowSize(width=window_w, height=window_h),
                ),
                context=browser_context_
        ) as browser_context:
            agent = CustomAgent(
                task=task,
                add_infos=add_infos,
                use_vision=use_vision,
                llm=llm,
                browser_context=browser_context,
                controller=controller,
                system_prompt_class=CustomSystemPrompt
            )
            history = await agent.run(max_steps=max_steps)

            final_result = history.final_result()
            errors = history.errors()
            model_actions = history.model_actions()
            model_thoughts = history.model_thoughts()

    except Exception as e:
        import traceback
        traceback.print_exc()
        final_result = ""
        errors = str(e) + "\n" + traceback.format_exc()
        model_actions = ""
        model_thoughts = ""
    finally:
        # 显式关闭持久化上下文
        if browser_context_:
            await browser_context_.close()

        # 关闭 Playwright 对象
        if playwright:
            await playwright.stop()
        await browser.close()
    return final_result, errors, model_actions, model_thoughts

import argparse
import gradio as gr
from gradio.themes import Base, Default, Soft, Monochrome, Glass, Origin, Citrus, Ocean
import os, glob

# Define the theme map globally
theme_map = {
    "Default": Default(),
    "Soft": Soft(),
    "Monochrome": Monochrome(),
    "Glass": Glass(),
    "Origin": Origin(),
    "Citrus": Citrus(),
    "Ocean": Ocean()
}

def create_ui(theme_name="Ocean"):
    """Create the UI with the specified theme"""
    # Enhanced styling for better visual appeal
    css = """
    .gradio-container {
        max-width: 1200px !important;
        margin: auto !important;
        padding-top: 20px !important;
    }
    .header-text {
        text-align: center;
        margin-bottom: 30px;
    }
    .theme-section {
        margin-bottom: 20px;
        padding: 15px;
        border-radius: 10px;
    }
    """
    
    with gr.Blocks(title="Browser Use WebUI", theme=theme_map[theme_name], css=css) as demo:
        with gr.Row():
            gr.Markdown(
                """
                # 🌐 Browser Use WebUI
                ### Control your browser with AI assistance
                """,
                elem_classes=["header-text"]
            )
        
        with gr.Tabs() as tabs:
            with gr.TabItem("🤖 Agent Settings", id=1):
                with gr.Group():
                    agent_type = gr.Radio(
                        ["org", "custom"],
                        label="Agent Type",
                        value="custom",
                        info="Select the type of agent to use"
                    )
                    max_steps = gr.Slider(
                        minimum=1,
                        maximum=200,
                        value=100,
                        step=1,
                        label="Max Run Steps",
                        info="Maximum number of steps the agent will take"
                    )
                    use_vision = gr.Checkbox(
                        label="Use Vision",
                        value=True,
                        info="Enable visual processing capabilities"
                    )

            with gr.TabItem("🔧 LLM Configuration", id=2):
                with gr.Group():
                    llm_provider = gr.Dropdown(
                        ["anthropic", "openai", "gemini", "azure_openai", "deepseek", "ollama"],
                        label="LLM Provider",
                        value="gemini",
                        info="Select your preferred language model provider"
                    )
                    llm_model_name = gr.Textbox(
                        label="Model Name",
                        value="gemini-2.0-flash-exp",
                        info="Specify the model to use"
                    )
                    llm_temperature = gr.Slider(
                        minimum=0.0,
                        maximum=2.0,
                        value=1.0,
                        step=0.1,
                        label="Temperature",
                        info="Controls randomness in model outputs"
                    )
                    with gr.Row():
                        llm_base_url = gr.Textbox(
                            label="Base URL",
                            info="API endpoint URL (if required)"
                        )
                        llm_api_key = gr.Textbox(
                            label="API Key",
                            type="password",
                            info="Your API key"
                        )

            with gr.TabItem("🌐 Browser Settings", id=3):
                with gr.Group():
                    with gr.Row():
                        use_own_browser = gr.Checkbox(
                            label="Use Own Browser",
                            value=False,
                            info="Use your existing browser instance"
                        )
                        headless = gr.Checkbox(
                            label="Headless Mode",
                            value=False,
                            info="Run browser without GUI"
                        )
                        disable_security = gr.Checkbox(
                            label="Disable Security",
                            value=True,
                            info="Disable browser security features"
                        )
                    
                    with gr.Row():
                        window_w = gr.Number(
                            label="Window Width",
                            value=1920,
                            info="Browser window width"
                        )
                        window_h = gr.Number(
                            label="Window Height",
                            value=1080,
                            info="Browser window height"
                        )
                    
                    save_recording_path = gr.Textbox(
                        label="Recording Path",
                        placeholder="e.g. ./tmp/record_videos",
                        value="./tmp/record_videos",
                        info="Path to save browser recordings"
                    )

            with gr.TabItem("📝 Task Settings", id=4):
                task = gr.Textbox(
                    label="Task Description",
                    lines=4,
                    placeholder="Enter your task here...",
                    value="go to google.com and type 'OpenAI' click search and give me the first url",
                    info="Describe what you want the agent to do"
                )
                add_infos = gr.Textbox(
                    label="Additional Information",
                    lines=3,
                    placeholder="Add any helpful context or instructions...",
                    info="Optional hints to help the LLM complete the task"
                )

                with gr.Row():
                    run_button = gr.Button("▶️ Run Agent", variant="primary", scale=2)
                    stop_button = gr.Button("⏹️ Stop", variant="stop", scale=1)

            with gr.TabItem("🎬 Recordings", id=5):
                def list_videos(path):
                    """Return the latest video file from the specified path."""
                    if not os.path.exists(path):
                        return ["Recording path not found"]
                    
                    # Get all video files in the directory
                    video_files = glob.glob(os.path.join(path, '*.[mM][pP]4')) + glob.glob(os.path.join(path, '*.[wW][eE][bB][mM]'))
                    
                    if not video_files:
                        return ["No recordings found"]
                    
                    # Sort files by modification time (latest first)
                    video_files.sort(key=os.path.getmtime, reverse=True)
                    
                    # Return only the latest video
                    return [video_files[0]]

                def display_videos(recording_path):
                    """Display the latest video in the gallery."""
                    return list_videos(recording_path)

                recording_display = gr.Gallery(label="Latest Recording", type="video")

                demo.load(
                    display_videos,
                    inputs=[save_recording_path],
                    outputs=[recording_display]
                )

                with gr.Group():
                    gr.Markdown("### Results")
                    with gr.Row():
                        with gr.Column():
                            final_result_output = gr.Textbox(
                                label="Final Result",
                                lines=3,
                                show_label=True
                            )
                        with gr.Column():
                            errors_output = gr.Textbox(
                                label="Errors",
                                lines=3,
                                show_label=True
                            )
                    with gr.Row():
                        with gr.Column():
                            model_actions_output = gr.Textbox(
                                label="Model Actions",
                                lines=3,
                                show_label=True
                            )
                        with gr.Column():
                            model_thoughts_output = gr.Textbox(
                                label="Model Thoughts",
                                lines=3,
                                show_label=True
                            )

        # Run button click handler
        run_button.click(
            fn=run_browser_agent,
            inputs=[
                agent_type, llm_provider, llm_model_name, llm_temperature,
                llm_base_url, llm_api_key, use_own_browser, headless,
                disable_security, window_w, window_h, save_recording_path,
                task, add_infos, max_steps, use_vision
            ],
            outputs=[final_result_output, errors_output, model_actions_output, model_thoughts_output]
        )

    return demo

def main():
    parser = argparse.ArgumentParser(description="Gradio UI for Browser Agent")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=7788, help="Port to listen on")
    parser.add_argument("--theme", type=str, default="Ocean", choices=theme_map.keys(), help="Theme to use for the UI")
    args = parser.parse_args()

    # Create the UI with the specified theme
    demo = create_ui(theme_name=args.theme)
    demo.launch(server_name=args.ip, server_port=args.port)

if __name__ == '__main__':
    main()
