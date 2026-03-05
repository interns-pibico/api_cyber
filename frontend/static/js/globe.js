import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ==================== CONFIG ====================
const R = 5;
const BG = 0x040d21;
const FPS = 30;
const INTERVAL = 1000 / FPS;
const IDLE_TIMEOUT = 4000;

const WATER_URL = 'https://cdn.jsdelivr.net/npm/three-globe@2.31.1/example/img/earth-water.png';

// Attack type colors
const ATTACK_COLORS = {
    SSH: 0xFF8FA3,
    Firewall: 0xFF8C00,
    Nginx: 0xFFD700,
    Sudo: 0x9B59B6,
    'High Risk': 0xCB4154,
    default: 0x4682B4,
};

// Severity colors
const SEVERITY_COLORS = {
    info: 0x28A745,
    low: 0x28A745,
    medium: 0xFFC107,
    high: 0xFF8C00,
    critical: 0xCB4154,
};

const TARGET_COLOR = 0x4682B4;

// ==================== STATE ====================
let scene, camera, renderer, controls;
let attackPoints = [], targetPoints = [], arcLines = [];
let animationFrameId = null;
let isRunning = false;
let raycaster, mouse;
let interactiveObjects = [];
let objectDataMap = new WeakMap();
let idleTimer = null;
let resizeObserver = null;
let lastFrame = 0;
let enterAnim = null;
let exitAnim = null;
let pendingRenderData = null;

// ==================== EASING ====================

function clamp01(t) { return Math.min(1, Math.max(0, t)); }
function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
function easeOutBack(t) {
    const c = 1.7;
    return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2);
}

// ==================== HELPERS ====================

function latLonToVec3(lat, lon, radius) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    return new THREE.Vector3(
        -radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta)
    );
}

function getAttackColor(attackTypes) {
    if (!attackTypes || attackTypes.length === 0) return ATTACK_COLORS.default;
    for (const t of attackTypes) {
        if (ATTACK_COLORS[t]) return ATTACK_COLORS[t];
    }
    return ATTACK_COLORS.default;
}

function getSeverityColor(severity) {
    return SEVERITY_COLORS[severity] || SEVERITY_COLORS.info;
}

function getAttackTypeCSSClass(type) {
    const map = { SSH: 'ssh', Firewall: 'firewall', Nginx: 'nginx', Sudo: 'sudo', 'High Risk': 'high-risk' };
    return map[type] || 'default';
}

// ==================== SCENE SETUP ====================

function initScene(container) {
    const w = container.clientWidth;
    const h = container.clientHeight;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(BG);

    camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 500);
    // On narrow screens (mobile), pull camera back so globe fits
    const aspect = w / h;
    const camZ = aspect < 1 ? 18 : aspect < 1.4 ? 16 : 14;
    camera.position.set(0, 2, camZ);

    renderer = new THREE.WebGLRenderer({ antialias: false });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.enablePan = false;
    controls.minDistance = 8;
    controls.maxDistance = 25;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.4;

    controls.addEventListener('start', () => {
        controls.autoRotate = false;
        clearTimeout(idleTimer);
    });
    controls.addEventListener('end', () => {
        idleTimer = setTimeout(() => { controls.autoRotate = true; }, IDLE_TIMEOUT);
    });

    // Minimal ambient (hologram self-illuminates)
    scene.add(new THREE.AmbientLight(0xffffff, 0.08));

    // Raycaster for interaction
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();
    renderer.domElement.addEventListener('mousemove', onMouseMove, false);
    renderer.domElement.addEventListener('click', onClick, false);

    // Resize observer (debounced to avoid excessive re-renders)
    let resizeTimer;
    resizeObserver = new ResizeObserver(() => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            const cw = container.clientWidth;
            const ch = container.clientHeight;
            camera.aspect = cw / ch;
            camera.updateProjectionMatrix();
            renderer.setSize(cw, ch);
        }, 150);
    });
    resizeObserver.observe(container);
}

// ==================== GLOBE VISUALS ====================

function createGlobe() {
    const loader = new THREE.TextureLoader();
    loader.load(WATER_URL, (waterTex) => {
        // Globe sphere with continent shapes
        const globeMat = new THREE.ShaderMaterial({
            uniforms: {
                tWater: { value: waterTex },
                uOceanColor: { value: new THREE.Color(0x2e8ad4) },
                uLandColor:  { value: new THREE.Color(0x5ec4f5) },
            },
            vertexShader: `
                varying vec2 vUv;
                varying vec3 vNormal;
                varying vec3 vPosition;
                void main() {
                    vUv = uv;
                    vNormal = normalize(normalMatrix * normal);
                    vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform sampler2D tWater;
                uniform vec3 uOceanColor;
                uniform vec3 uLandColor;
                varying vec2 vUv;
                varying vec3 vNormal;
                varying vec3 vPosition;

                void main() {
                    float water = texture2D(tWater, vUv).r;
                    float isLand = 1.0 - step(0.5, water);
                    vec3 color = mix(uOceanColor, uLandColor, isLand);

                    vec3 viewDir = normalize(-vPosition);
                    float fresnel = 1.0 - dot(vNormal, viewDir);
                    float rimSoft = pow(fresnel, 1.5) * 0.7;
                    float rimHard = pow(fresnel, 4.0) * 1.2;
                    color += vec3(0.25, 0.55, 0.85) * (rimSoft + rimHard);

                    float gradient = vNormal.y * 0.1 + 0.5;
                    color *= (0.85 + gradient * 0.3);

                    gl_FragColor = vec4(color, 1.0);
                }
            `,
        });
        scene.add(new THREE.Mesh(new THREE.SphereGeometry(R, 64, 48), globeMat));

        // Low-poly wireframe mesh
        const icoGeo = new THREE.IcosahedronGeometry(R + 0.03, 4);
        scene.add(new THREE.Mesh(icoGeo, new THREE.MeshBasicMaterial({
            color: 0x60c8ff, wireframe: true, transparent: true, opacity: 0.12,
        })));

        // Vertex dots
        const verts = icoGeo.attributes.position;
        const seen = new Set();
        const dotPositions = [];
        for (let i = 0; i < verts.count; i++) {
            const x = verts.getX(i).toFixed(3);
            const y = verts.getY(i).toFixed(3);
            const z = verts.getZ(i).toFixed(3);
            const key = `${x},${y},${z}`;
            if (!seen.has(key)) {
                seen.add(key);
                dotPositions.push(parseFloat(x), parseFloat(y), parseFloat(z));
            }
        }
        const dotGeo = new THREE.BufferGeometry();
        dotGeo.setAttribute('position', new THREE.Float32BufferAttribute(dotPositions, 3));
        scene.add(new THREE.Points(dotGeo, new THREE.PointsMaterial({
            color: 0x80d4ff, size: 0.08, sizeAttenuation: true, transparent: true, opacity: 0.7,
        })));

        // Atmosphere glow
        const atmosMat = new THREE.ShaderMaterial({
            vertexShader: `
                varying vec3 vNormal;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                varying vec3 vNormal;
                void main() {
                    float intensity = pow(0.65 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
                    gl_FragColor = vec4(0.25, 0.55, 0.85, 1.0) * intensity * 1.6;
                }
            `,
            blending: THREE.AdditiveBlending,
            side: THREE.BackSide,
            transparent: true,
        });
        scene.add(new THREE.Mesh(new THREE.SphereGeometry(R * 1.08, 32, 24), atmosMat));

        // Stars
        const starGeo = new THREE.BufferGeometry();
        const starPos = new Float32Array(800 * 3);
        for (let i = 0; i < 800 * 3; i += 3) {
            const r2 = 60 + Math.random() * 100;
            const t = Math.random() * Math.PI * 2;
            const p = Math.acos(2 * Math.random() - 1);
            starPos[i]   = r2 * Math.sin(p) * Math.cos(t);
            starPos[i+1] = r2 * Math.sin(p) * Math.sin(t);
            starPos[i+2] = r2 * Math.cos(p);
        }
        starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3));
        scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({
            color: 0xffffff, size: 0.35, sizeAttenuation: true,
        })));

        // Hide loading once globe is built
        const loading = document.getElementById('globeLoading');
        if (loading) loading.style.display = 'none';
    });
}

// ==================== ATTACK / TARGET / ARC creation is handled in renderAttackData ====================

// ==================== EXIT ANIMATION ====================

function startExitAnimation() {
    enterAnim = null;

    // Snap arcs to full draw so retract starts from full length
    arcLines.forEach(line => {
        const total = line.geometry.attributes.position.count;
        line.geometry.setDrawRange(0, total);
    });

    const nonRings = attackPoints.filter(o => !o.userData.isPulse);
    const rings = attackPoints.filter(o => o.userData.isPulse);

    // Cap total stagger so exit completes in ~1.5s regardless of element count
    const ptStep  = nonRings.length  > 1 ? Math.min(0.04, 0.5 / (nonRings.length  - 1)) : 0;
    const arcStep = arcLines.length  > 1 ? Math.min(0.04, 0.7 / (arcLines.length  - 1)) : 0;

    const pointEnd = nonRings.length > 0 ? (nonRings.length - 1) * ptStep  + 0.35 : 0;
    const arcEnd   = arcLines.length > 0 ? (arcLines.length  - 1) * arcStep + 0.55 : 0;

    exitAnim = {
        startTime: performance.now() / 1000,
        points: nonRings.map((mesh, i) => ({ mesh, delay: i * ptStep,  duration: 0.35 })),
        rings:  rings.map((mesh, i)    => ({ mesh, delay: i * ptStep,  duration: 0.35 })),
        arcs: arcLines.map((line, i)   => ({
            line, delay: i * arcStep, duration: 0.55,
            totalPts: line.geometry.attributes.position.count,
        })),
        targetDelay: Math.max(pointEnd, arcEnd),
        targetDuration: 0.3,
        totalDuration: Math.max(pointEnd, arcEnd) + 0.3,
    };
}

// ==================== ANIMATION ====================

function animate(time) {
    if (!isRunning) return;
    animationFrameId = requestAnimationFrame(animate);

    if (time - lastFrame < INTERVAL) return;
    lastFrame = time;

    const now = performance.now() / 1000;

    if (exitAnim) {
        // === EXIT ANIMATION (reverse Disney) ===
        const elapsed = now - exitAnim.startTime;

        // 1. Attack points shrink staggered
        exitAnim.points.forEach(p => {
            const t = clamp01((elapsed - p.delay) / p.duration);
            const s = 1 - easeOutCubic(t);
            p.mesh.scale.set(s, s, s);
        });

        // Rings shrink with points
        exitAnim.rings.forEach(r => {
            const t = clamp01((elapsed - r.delay) / r.duration);
            const s = 1 - easeOutCubic(t);
            r.mesh.scale.set(s, s, s);
            r.mesh.material.opacity = 0.4 * s;
        });

        // 2. Arcs retract toward server
        exitAnim.arcs.forEach(a => {
            const t = clamp01((elapsed - a.delay) / a.duration);
            const remaining = Math.floor((1 - easeOutCubic(t)) * a.totalPts);
            a.line.geometry.setDrawRange(0, Math.max(0, remaining));
        });

        // 3. Target shrinks last
        const tTarget = clamp01((elapsed - exitAnim.targetDelay) / exitAnim.targetDuration);
        const sTarget = 1 - easeOutCubic(tTarget);
        targetPoints.forEach(obj => {
            obj.scale.set(sTarget, sTarget, sTarget);
        });

        // Exit complete → clear and start enter with pending data
        if (elapsed >= exitAnim.totalDuration) {
            exitAnim = null;
            clearAttackPoints();
            clearTargetPoints();
            clearArcs();
            interactiveObjects = [];

            if (pendingRenderData) {
                const data = pendingRenderData;
                pendingRenderData = null;
                startEnterAnimation(data);
            }
        }
    } else if (enterAnim) {
        // === ENTER ANIMATION (Disney-style) ===
        const elapsed = now - enterAnim.startTime;

        // 1. Targets pop in first
        const tTarget = Math.min(1, elapsed / enterAnim.targetDuration);
        const sTarget = easeOutBack(tTarget);
        targetPoints.forEach(obj => {
            if (obj.userData.isTarget) {
                obj.scale.set(sTarget, sTarget, sTarget);
                obj.rotation.y += 0.01;
            }
        });

        // 2. Arcs draw outward from server
        let allArcsDone = enterAnim.arcs.length === 0;
        enterAnim.arcs.forEach(a => {
            if (a.done) return;
            const t = (elapsed - a.delay) / a.duration;
            if (t < 0) { allArcsDone = false; return; }
            if (t >= 1) {
                a.line.geometry.setDrawRange(0, a.totalPts);
                a.done = true;
                const pt = enterAnim.points.get(a.sourceIp);
                if (pt && !pt.popped) {
                    pt.popped = true;
                    pt.popStart = now;
                }
            } else {
                allArcsDone = false;
                a.line.geometry.setDrawRange(0, Math.floor(easeOutCubic(t) * a.totalPts));
            }
        });

        // Pop orphan source points when all arcs done
        if (allArcsDone) {
            enterAnim.points.forEach(pt => {
                if (!pt.popped) { pt.popped = true; pt.popStart = now; }
            });
        }

        // 3. Attack point pops (easeOutBack bounce)
        let allPointsDone = enterAnim.points.size === 0;
        enterAnim.points.forEach(pt => {
            if (pt.popped) {
                const popT = Math.min(1, (now - pt.popStart) / 0.35);
                const s = easeOutBack(popT);
                pt.mesh.scale.set(s, s, s);
                pt.rings.forEach(r => {
                    r.scale.set(s, s, s);
                    r.material.opacity = 0.4 * s;
                });
                if (popT < 1) allPointsDone = false;
            } else {
                allPointsDone = false;
            }
        });

        // All done → transition to active phase
        if (allArcsDone && allPointsDone && tTarget >= 1) {
            enterAnim = null;
            arcLines.forEach(line => {
                line.userData.progress = 0.7 + Math.random() * 0.6;
            });
        }
    } else {
        // === ACTIVE PHASE (normal loop) ===

        // Pulse rings
        attackPoints.forEach(obj => {
            if (obj.userData.isPulse) {
                const s = 1 + 0.3 * Math.sin(now * 2);
                obj.scale.set(s, s, s);
                obj.material.opacity = 0.2 + 0.2 * Math.sin(now * 2);
            }
        });

        // Target rotation
        targetPoints.forEach(obj => {
            if (obj.userData.isTarget) obj.rotation.y += 0.01;
        });

        // Arcs stay fully drawn after enter animation
        arcLines.forEach(line => {
            const total = line.geometry.attributes.position.count;
            line.geometry.setDrawRange(0, total);
        });
    }

    controls.update();
    renderer.render(scene, camera);
}

// ==================== INTERACTION ====================

function onMouseMove(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(interactiveObjects);
    renderer.domElement.style.cursor = intersects.length > 0 ? 'pointer' : 'default';
}

function onClick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(interactiveObjects);

    if (intersects.length > 0) {
        const obj = intersects[0].object;
        const info = objectDataMap.get(obj);
        if (info) {
            // Source clicks open the DetailPanel IP view
            if (info.type === 'source' && typeof DetailPanel !== 'undefined') {
                DetailPanel.showIP(info.data.ip);
            } else if (info.type === 'target' && typeof DetailPanel !== 'undefined') {
                DetailPanel.showAgent(info.data.agent_id);
            } else {
                showInfoPanel(info);
            }
        }
    }
}

function showInfoPanel(info) {
    const panel = document.getElementById('globeInfoPanel');
    const content = document.getElementById('globeInfoContent');
    if (!panel || !content) return;

    if (info.type === 'source') {
        const s = info.data;
        const typeBadges = s.attack_types.map(t =>
            `<span class="attack-type-badge ${getAttackTypeCSSClass(t)}">${t}</span>`
        ).join('');

        content.innerHTML = `
            <h4><i class="fas fa-crosshairs" style="color:#CB4154"></i> Atacante</h4>
            <div class="info-row"><span class="label">IP</span><span class="value">${s.ip}</span></div>
            <div class="info-row"><span class="label">Pa\u00eds</span><span class="value">${s.country_name} (${s.country_code})</span></div>
            ${s.city ? `<div class="info-row"><span class="label">Ciudad</span><span class="value">${s.city}</span></div>` : ''}
            <div class="info-row"><span class="label">Total hits</span><span class="value">${s.total_hits}</span></div>
            <div class="info-row"><span class="label">Severidad m\u00e1x</span><span class="value" style="color:${new THREE.Color(getSeverityColor(s.max_severity)).getStyle()}">${s.max_severity}</span></div>
            ${s.threat_score > 0 ? `<div class="info-row"><span class="label">Threat Score</span><span class="value">${s.threat_score.toFixed(1)}</span></div>` : ''}
            <div class="info-row"><span class="label">Alto riesgo</span><span class="value">${s.is_high_risk ? 'S\u00ed' : 'No'}</span></div>
            <div class="attack-types">${typeBadges}</div>
        `;
    } else {
        const t = info.data;
        content.innerHTML = `
            <h4><i class="fas fa-server" style="color:#4682B4"></i> Servidor</h4>
            <div class="info-row"><span class="label">Hostname</span><span class="value">${t.hostname}</span></div>
            <div class="info-row"><span class="label">IP</span><span class="value">${t.ip_address || 'N/A'}</span></div>
            <div class="info-row"><span class="label">OS</span><span class="value">${t.os_type}</span></div>
            <div class="info-row"><span class="label">Ataques recibidos</span><span class="value">${t.attack_count}</span></div>
        `;
    }

    panel.classList.add('visible');
}

// ==================== CLEANUP ====================

function clearAttackPoints() {
    attackPoints.forEach(obj => {
        scene.remove(obj);
        obj.geometry?.dispose();
        obj.material?.dispose();
    });
    attackPoints = [];
}

function clearTargetPoints() {
    targetPoints.forEach(obj => {
        scene.remove(obj);
        obj.geometry?.dispose();
        obj.material?.dispose();
    });
    targetPoints = [];
}

function clearArcs() {
    arcLines.forEach(line => {
        scene.remove(line);
        line.geometry?.dispose();
        line.material?.dispose();
    });
    arcLines = [];
}

function disposeScene() {
    enterAnim = null;
    exitAnim = null;
    pendingRenderData = null;
    clearAttackPoints();
    clearTargetPoints();
    clearArcs();

    if (renderer) {
        renderer.domElement.removeEventListener('mousemove', onMouseMove);
        renderer.domElement.removeEventListener('click', onClick);
        renderer.dispose();
        renderer.domElement.remove();
        renderer = null;
    }

    if (controls) { controls.dispose(); controls = null; }
    if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null; }

    // Dispose all remaining scene objects
    if (scene) {
        scene.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (obj.material.map) obj.material.map.dispose();
                obj.material.dispose();
            }
        });
        scene = null;
    }

    camera = null;
    interactiveObjects = [];
    objectDataMap = new WeakMap();
}

// ==================== PUBLIC API ====================

function checkWebGL() {
    try {
        const c = document.createElement('canvas');
        return !!(c.getContext('webgl2') || c.getContext('webgl'));
    } catch { return false; }
}

window.startGlobe = function () {
    if (isRunning) return;

    const container = document.getElementById('globeCanvasContainer');
    const loading = document.getElementById('globeLoading');
    const fallback = document.getElementById('globeFallback');

    if (!container) return;

    if (!checkWebGL()) {
        if (fallback) fallback.classList.add('visible');
        if (loading) loading.style.display = 'none';
        return;
    }

    if (scene) disposeScene();
    if (loading) loading.style.display = 'flex';

    initScene(container);
    createGlobe();

    isRunning = true;
    lastFrame = 0;
    animate(0);
};

window.stopGlobe = function () {
    isRunning = false;
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    clearTimeout(idleTimer);
    disposeScene();
};

function startEnterAnimation(data) {
    clearAttackPoints();
    clearTargetPoints();
    clearArcs();
    interactiveObjects = [];
    enterAnim = null;

    // 1. Create target points at scale 0 (pop in first)
    (data.targets || []).forEach(target => {
        const pos = latLonToVec3(target.latitude, target.longitude, R + 0.03);
        const geo = new THREE.OctahedronGeometry(0.1, 0);
        const mat = new THREE.MeshBasicMaterial({ color: TARGET_COLOR });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.copy(pos);
        mesh.userData.isTarget = true;
        mesh.scale.set(0, 0, 0);
        scene.add(mesh);
        targetPoints.push(mesh);
        interactiveObjects.push(mesh);
        objectDataMap.set(mesh, { type: 'target', data: target });
    });

    // 2. Create attack points at scale 0 (pop when arc lands)
    const pointMap = new Map();
    (data.sources || []).forEach(source => {
        const pos = latLonToVec3(source.latitude, source.longitude, R + 0.02);
        const size = Math.max(0.04, Math.min(0.15, source.total_hits / 50));
        const color = getSeverityColor(source.max_severity);

        const geo = new THREE.SphereGeometry(size, 12, 12);
        const mat = new THREE.MeshBasicMaterial({ color });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.copy(pos);
        mesh.scale.set(0, 0, 0);
        scene.add(mesh);
        attackPoints.push(mesh);
        interactiveObjects.push(mesh);
        objectDataMap.set(mesh, { type: 'source', data: source });

        const rings = [];
        if (source.is_high_risk) {
            const ringGeo = new THREE.RingGeometry(size * 1.5, size * 2.2, 24);
            const ringMat = new THREE.MeshBasicMaterial({
                color, transparent: true, opacity: 0, side: THREE.DoubleSide,
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.position.copy(pos);
            ring.lookAt(new THREE.Vector3(0, 0, 0));
            ring.userData.isPulse = true;
            ring.scale.set(0, 0, 0);
            scene.add(ring);
            attackPoints.push(ring);
            rings.push(ring);
        }

        pointMap.set(source.ip, { mesh, rings, popped: false, popStart: 0 });
    });

    // 3. Create arcs: TARGET → SOURCE (server radiates outward, Disney-style)
    const arcAnims = [];
    // Cap total stagger so all arcs start within 0.8s
    const enterArcStep = (data.arcs || []).length > 1
        ? Math.min(0.04, 0.8 / ((data.arcs.length) - 1))
        : 0;
    (data.arcs || []).forEach((arc, i) => {
        const start = latLonToVec3(arc.target_lat, arc.target_lon, R + 0.03);
        const end   = latLonToVec3(arc.source_lat, arc.source_lon, R + 0.02);

        const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
        const dist = start.distanceTo(end);
        mid.normalize().multiplyScalar(R + 0.8 + dist * 0.35);

        const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
        const pts = curve.getPoints(40);
        const geometry = new THREE.BufferGeometry().setFromPoints(pts);
        geometry.setDrawRange(0, 0);

        const color = ATTACK_COLORS[arc.attack_type] || ATTACK_COLORS.default;
        const material = new THREE.LineBasicMaterial({
            color, transparent: true, opacity: 0.85,
        });

        const line = new THREE.Line(geometry, material);
        scene.add(line);
        arcLines.push(line);

        arcAnims.push({
            line,
            delay: 0.3 + i * enterArcStep,
            duration: Math.min(0.6 + dist * 0.04, 1.0),
            sourceIp: arc.source_ip,
            totalPts: 41,
            done: false,
        });
    });

    // Start enter animation
    enterAnim = {
        startTime: performance.now() / 1000,
        targetDuration: 0.35,
        arcs: arcAnims,
        points: pointMap,
    };
}

window.renderAttackData = function (data) {
    if (!scene) return;

    const loading = document.getElementById('globeLoading');
    if (loading) loading.style.display = 'none';

    // If already exiting, just update the pending data
    if (exitAnim) {
        pendingRenderData = data;
        return;
    }

    // If there's data on screen, play exit animation first
    if (attackPoints.length > 0 || arcLines.length > 0 || targetPoints.length > 0) {
        pendingRenderData = data;
        startExitAnimation();
        return;
    }

    // No existing data → enter directly
    startEnterAnimation(data);
};
