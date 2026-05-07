import { buildRenderData } from "./renderData.js";

export class WebGpuRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ready = false;
        this.summary = "Inicializando WebGPU";
        this.maxShapes = 4096;
        this.maxLineVertices = 24000;
    }

    async init() {
        if (!navigator.gpu) return false;

        let adapter;
        try {
            adapter = await navigator.gpu.requestAdapter();
        } catch (error) {
            console.warn(error);
            return false;
        }
        if (!adapter) return false;

        try {
            this.device = await adapter.requestDevice();
            this.context = this.canvas.getContext("webgpu");
        } catch (error) {
            console.warn(error);
            return false;
        }
        if (!this.context) return false;

        this.format = navigator.gpu.getPreferredCanvasFormat();
        try {
            this.context.configure({ device: this.device, format: this.format, alphaMode: "opaque" });
        } catch (error) {
            console.warn(error);
            return false;
        }
        this.createBuffers();
        this.createPipelines();
        this.ready = true;
        this.summary = "WebGPU ativo";
        return true;
    }

    createBuffers() {
        this.quadBuffer = this.device.createBuffer({
            size: 8 * 4,
            usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
        });
        this.device.queue.writeBuffer(this.quadBuffer, 0, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]));
        this.shapeBuffer = this.device.createBuffer({
            size: this.maxShapes * 10 * 4,
            usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
        });
        this.lineBuffer = this.device.createBuffer({
            size: this.maxLineVertices * 6 * 4,
            usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
        });
    }

    createPipelines() {
        const shapeShader = this.device.createShaderModule({ code: `
            struct VertexOut {
                @builtin(position) position: vec4f,
                @location(0) local: vec2f,
                @location(1) color: vec4f,
                @location(2) shape: f32,
            };
            @vertex
            fn vs(
                @location(0) local: vec2f,
                @location(1) center: vec2f,
                @location(2) halfSize: vec2f,
                @location(3) color: vec4f,
                @location(4) shape: f32
            ) -> VertexOut {
                var out: VertexOut;
                out.position = vec4f(center + local * halfSize, 0.0, 1.0);
                out.local = local;
                out.color = color;
                out.shape = shape;
                return out;
            }
            @fragment
            fn fs(in: VertexOut) -> @location(0) vec4f {
                if (in.shape < 0.5 && length(in.local) > 1.0) {
                    discard;
                }
                return in.color;
            }
        ` });

        this.shapePipeline = this.device.createRenderPipeline({
            layout: "auto",
            vertex: {
                module: shapeShader,
                entryPoint: "vs",
                buffers: [
                    { arrayStride: 8, attributes: [{ shaderLocation: 0, offset: 0, format: "float32x2" }] },
                    {
                        arrayStride: 40,
                        stepMode: "instance",
                        attributes: [
                            { shaderLocation: 1, offset: 0, format: "float32x2" },
                            { shaderLocation: 2, offset: 8, format: "float32x2" },
                            { shaderLocation: 3, offset: 16, format: "float32x4" },
                            { shaderLocation: 4, offset: 32, format: "float32" },
                        ],
                    },
                ],
            },
            fragment: {
                module: shapeShader,
                entryPoint: "fs",
                targets: [{ format: this.format, blend: {
                    color: { srcFactor: "src-alpha", dstFactor: "one-minus-src-alpha" },
                    alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha" },
                } }],
            },
            primitive: { topology: "triangle-strip" },
        });

        const lineShader = this.device.createShaderModule({ code: `
            struct VertexOut {
                @builtin(position) position: vec4f,
                @location(0) color: vec4f,
            };
            @vertex
            fn vs(@location(0) position: vec2f, @location(1) color: vec4f) -> VertexOut {
                var out: VertexOut;
                out.position = vec4f(position, 0.0, 1.0);
                out.color = color;
                return out;
            }
            @fragment
            fn fs(in: VertexOut) -> @location(0) vec4f {
                return in.color;
            }
        ` });

        this.linePipeline = this.device.createRenderPipeline({
            layout: "auto",
            vertex: {
                module: lineShader,
                entryPoint: "vs",
                buffers: [{
                    arrayStride: 24,
                    attributes: [
                        { shaderLocation: 0, offset: 0, format: "float32x2" },
                        { shaderLocation: 1, offset: 8, format: "float32x4" },
                    ],
                }],
            },
            fragment: {
                module: lineShader,
                entryPoint: "fs",
                targets: [{ format: this.format, blend: {
                    color: { srcFactor: "src-alpha", dstFactor: "one-minus-src-alpha" },
                    alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha" },
                } }],
            },
            primitive: { topology: "line-list" },
        });
    }

    resize() {
        if (this.ready) {
            this.context.configure({ device: this.device, format: this.format, alphaMode: "opaque" });
        }
    }

    render(state, params) {
        if (!this.ready) return;
        const data = buildRenderData(this.canvas, state, params, this);
        if (data.shapeCount > 0) this.device.queue.writeBuffer(this.shapeBuffer, 0, data.shapes);
        if (data.lineVertexCount > 0) this.device.queue.writeBuffer(this.lineBuffer, 0, data.lines);

        const encoder = this.device.createCommandEncoder();
        const pass = encoder.beginRenderPass({
            colorAttachments: [{
                view: this.context.getCurrentTexture().createView(),
                clearValue: { r: 0.972, g: 0.984, b: 1, a: 1 },
                loadOp: "clear",
                storeOp: "store",
            }],
        });

        pass.setPipeline(this.linePipeline);
        pass.setVertexBuffer(0, this.lineBuffer);
        pass.draw(data.lineVertexCount);
        pass.setPipeline(this.shapePipeline);
        pass.setVertexBuffer(0, this.quadBuffer);
        pass.setVertexBuffer(1, this.shapeBuffer);
        pass.draw(4, data.shapeCount);
        pass.end();
        this.device.queue.submit([encoder.finish()]);
    }
}
