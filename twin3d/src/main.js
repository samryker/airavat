// Import Three.js and related modules
import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// will hold { "Kidney-Left": Mesh, ... }
let markers = {};
let prevHighlight = null;
let currentScene = null;
let currentMesh = null;
let isInitialized = false; // Flag to prevent double initialization

// SMPL API configuration
const SMPL_API_BASE = 'https://airavat-backend-u3hyo7liyq-uc.a.run.app';

// Function to load SMPL model dynamically
async function loadSMPLModel(patientId, height, weight, gender) {
  try {
    console.log(`🔄 Loading SMPL model for patient ${patientId}: height=${height}, weight=${weight}, gender=${gender}`);
    console.log(`🌐 Making request to: ${SMPL_API_BASE}/smpl/generate`);
    
    // Call SMPL API to generate mesh
    const response = await fetch(`${SMPL_API_BASE}/smpl/generate?patient_id=${patientId}&height=${height}&weight=${weight}&gender=${gender}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      mode: 'cors' // Explicitly set CORS mode
    });
    
    console.log(`📡 Response status: ${response.status} ${response.statusText}`);
    console.log(`📡 Response headers:`, response.headers);
    
    if (!response.ok) {
      throw new Error(`SMPL API error: ${response.status} - ${response.statusText}`);
    }
    
    const meshData = await response.json();
    console.log('✅ SMPL mesh data received:', meshData);
    
    // For now, create a dynamic placeholder based on parameters
    // In a full implementation, this would load the actual GLB file
    return createDynamicSMPLModel(meshData.parameters || { height, weight, gender, bmi: (weight / Math.pow(height/100, 2)).toFixed(1) });
    
  } catch (error) {
    console.error('❌ Error loading SMPL model:', error);
    console.error('🔍 Error details:', error.message);
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      console.error('🌐 This might be a CORS issue. Check if the backend allows requests from localhost:3000');
    }
    // Don't fallback to OBJ - just return null
    return null;
  }
}

// Create dynamic SMPL model based on parameters
function createDynamicSMPLModel(parameters) {
  if (!currentScene) {
    console.error('❌ No current scene available');
    return null;
  }
  
  // Clear existing mesh
  if (currentMesh) {
    currentScene.remove(currentMesh);
  }
  
  const { height = 170, weight = 70, gender = 'neutral', bmi = 24.2 } = parameters;
  
  console.log(`🎨 Creating dynamic SMPL model with parameters:`, parameters);
  
  // Create a more detailed humanoid model based on parameters
  const group = new THREE.Group();
  
  // Scale factor based on height
  const heightScale = height / 170.0; // Normalize to 170cm
  const weightScale = weight / 70.0; // Normalize to 70kg
  
  // Make the model much larger for visibility
  const overallScale = 2.0; // Scale everything up by 2x
  
  // Create head
  const headGeometry = new THREE.SphereGeometry(0.15 * heightScale * overallScale, 32, 32);
  const headMaterial = new THREE.MeshPhongMaterial({ color: 0xffdbac, shininess: 30 });
  const head = new THREE.Mesh(headGeometry, headMaterial);
  head.position.y = 1.6 * heightScale * overallScale;
  group.add(head);
  
  // Create torso
  const torsoGeometry = new THREE.CylinderGeometry(0.3 * weightScale * overallScale, 0.25 * weightScale * overallScale, 0.8 * heightScale * overallScale, 32);
  const torsoMaterial = new THREE.MeshPhongMaterial({ color: 0x4a90e2, shininess: 30 });
  const torso = new THREE.Mesh(torsoGeometry, torsoMaterial);
  torso.position.y = 1.1 * heightScale * overallScale;
  group.add(torso);
  
  // Create arms
  const armGeometry = new THREE.CylinderGeometry(0.05 * heightScale * overallScale, 0.05 * heightScale * overallScale, 0.6 * heightScale * overallScale, 16);
  const armMaterial = new THREE.MeshPhongMaterial({ color: 0xffdbac, shininess: 30 });
  
  const leftArm = new THREE.Mesh(armGeometry, armMaterial);
  leftArm.position.set(-0.35 * weightScale * overallScale, 1.2 * heightScale * overallScale, 0);
  leftArm.rotation.z = Math.PI / 6;
  group.add(leftArm);
  
  const rightArm = new THREE.Mesh(armGeometry, armMaterial);
  rightArm.position.set(0.35 * weightScale * overallScale, 1.2 * heightScale * overallScale, 0);
  rightArm.rotation.z = -Math.PI / 6;
  group.add(rightArm);
  
  // Create legs
  const legGeometry = new THREE.CylinderGeometry(0.08 * heightScale * overallScale, 0.08 * heightScale * overallScale, 0.8 * heightScale * overallScale, 16);
  const legMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50, shininess: 30 });
  
  const leftLeg = new THREE.Mesh(legGeometry, legMaterial);
  leftLeg.position.set(-0.15 * weightScale * overallScale, 0.4 * heightScale * overallScale, 0);
  group.add(leftLeg);
  
  const rightLeg = new THREE.Mesh(legGeometry, legMaterial);
  rightLeg.position.set(0.15 * weightScale * overallScale, 0.4 * heightScale * overallScale, 0);
  group.add(rightLeg);
  
  // Add anatomical markers
  addAnatomicalMarkers(group, parameters, overallScale);
  
  // Add dynamic labels
  addDynamicLabels(group, parameters);
  
  currentScene.add(group);
  currentMesh = group;
  
  // Add debugging - show bounding box
  const box = new THREE.Box3().setFromObject(group);
  const boxHelper = new THREE.Box3Helper(box, 0xffff00);
  currentScene.add(boxHelper);
  
  // Add a grid helper to see the ground plane
  const gridHelper = new THREE.GridHelper(10, 10);
  currentScene.add(gridHelper);
  
  // Add axes helper
  const axesHelper = new THREE.AxesHelper(2);
  currentScene.add(axesHelper);
  
  // Add a bright outline to the SMPL model
  const edges = new THREE.EdgesGeometry(torsoGeometry);
  const outline = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 3 })
  );
  outline.position.copy(torso.position);
  group.add(outline);
  
  console.log(`✅ Dynamic SMPL model created for ${gender} patient: height=${height}cm, weight=${weight}kg, BMI=${bmi}`);
  console.log(`📍 Model position:`, group.position);
  console.log(`📦 Model bounding box:`, box.min, 'to', box.max);
  
  return group;
}

// Add anatomical markers to the model
function addAnatomicalMarkers(group, parameters, overallScale) {
  const { height = 170, weight = 70 } = parameters;
  const heightScale = height / 170.0;
  const weightScale = weight / 70.0;
  
  const organs = [
    { name: 'Heart', position: [0, 1.3 * heightScale, 0.1 * weightScale], color: 0xff0000 },
    { name: 'Lungs', position: [0, 1.2 * heightScale, 0.15 * weightScale], color: 0x00ff00 },
    { name: 'Liver', position: [0.1 * weightScale, 0.9 * heightScale, 0.1 * weightScale], color: 0xffff00 },
    { name: 'Kidney-Left', position: [-0.2 * weightScale, 0.8 * heightScale, 0.1 * weightScale], color: 0x00ffff },
    { name: 'Kidney-Right', position: [0.2 * weightScale, 0.8 * heightScale, 0.1 * weightScale], color: 0x00ffff },
    { name: 'Stomach', position: [0, 0.9 * heightScale, 0.2 * weightScale], color: 0xff00ff },
    { name: 'Pancreas', position: [0.05 * weightScale, 0.85 * heightScale, 0.15 * weightScale], color: 0xff8800 }, // Added Pancreas
    { name: 'Femur', position: [0, 0.2 * heightScale, 0.1 * weightScale], color: 0x0000ff }, // Added Femur
  ];
  
  organs.forEach(organ => {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.1 * heightScale * overallScale, 16, 16), // Much bigger markers
      new THREE.MeshPhongMaterial({ 
        color: organ.color, 
        emissive: organ.color,
        emissiveIntensity: 0.8, // Brighter glow
        shininess: 100,
        transparent: true,
        opacity: 0.9
      })
    );
    marker.name = organ.name;
    marker.position.set(...organ.position.map(p => p * overallScale)); // Scale positions too
    group.add(marker);
    markers[organ.name] = marker;
    console.log(`🔖 Added marker for ${organ.name} at position:`, marker.position);
  });
}

// Add dynamic labels showing parameters
function addDynamicLabels(group, parameters) {
  const { height = 170, weight = 70, gender = 'neutral', bmi = 24.2 } = parameters;
  
  // Create a simple text display using a plane with texture
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  canvas.width = 256;
  canvas.height = 128;
  
  context.fillStyle = 'rgba(0, 0, 0, 0.8)';
  context.fillRect(0, 0, canvas.width, canvas.height);
  
  context.fillStyle = 'white';
  context.font = '16px Arial';
  context.textAlign = 'center';
  context.fillText(`Height: ${height}cm`, canvas.width/2, 30);
  context.fillText(`Weight: ${weight}kg`, canvas.width/2, 50);
  context.fillText(`Gender: ${gender}`, canvas.width/2, 70);
  context.fillText(`BMI: ${bmi}`, canvas.width/2, 90);
  
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true });
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(1, 0.5), material);
  plane.position.set(0, 2 * (height / 170.0), 0);
  group.add(plane);
}

// Add a simple fallback model if everything else fails
function createFallbackModel() {
  console.log('🔄 Creating fallback cube model...');
  
  if (!currentScene) {
    console.error('❌ No current scene available for fallback');
    return;
  }
  
  // Clear existing mesh
  if (currentMesh) {
    currentScene.remove(currentMesh);
  }
  
  // Create a simple cube as fallback
  const geometry = new THREE.BoxGeometry(1, 2, 0.5);
  const material = new THREE.MeshLambertMaterial({ color: 0x4a90e2 });
  const cube = new THREE.Mesh(geometry, material);
  
  // Add some basic markers
  const markerData = [
    { name: 'Heart', position: [0, 0.5, 0.2], color: 0xff0000 },
    { name: 'Kidney-Left', position: [-0.3, 0, 0.2], color: 0x00ff00 },
    { name: 'Kidney-Right', position: [0.3, 0, 0.2], color: 0x00ff00 },
    { name: 'Stomach', position: [0, 0, 0.3], color: 0xffff00 },
  ];
  
  markerData.forEach(marker => {
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.1, 16, 16),
      new THREE.MeshStandardMaterial({ color: marker.color, emissive: marker.color })
    );
    sphere.name = marker.name;
    sphere.position.set(...marker.position);
    cube.add(sphere);
    markers[marker.name] = sphere;
  });
  
  currentScene.add(cube);
  currentMesh = cube;
  
  console.log('✅ Fallback cube model created');
  return cube;
}

// Expose functions to window for Flutter to call
window.loadSMPLAvatar = async function(patientId, height, weight, gender) {
  console.log(`🎯 Loading SMPL avatar for patient ${patientId}`);
  return await loadSMPLModel(patientId, height, weight, gender);
};

window.updateSMPLParameters = async function(height, weight, gender) {
  console.log(`🔄 Updating SMPL parameters: height=${height}, weight=${weight}, gender=${gender}`);
  return await loadSMPLModel('current_user', height, weight, gender);
};

window.getSMPLHealth = async function() {
  try {
    console.log('🏥 Checking SMPL API health...');
    const response = await fetch(`${SMPL_API_BASE}/smpl/health`);
    const health = await response.json();
    console.log('✅ SMPL health check result:', health);
    return health;
  } catch (error) {
    console.error('❌ SMPL health check failed:', error);
    return { status: 'error', message: error.message };
  }
};

window.getCurrentMode = function() {
  return {
    currentMesh: currentMesh ? 'SMPL' : 'OBJ',
    parameters: currentMesh ? 'Dynamic' : 'Static'
  };
};

// Expose fallback model function
window.createFallbackModel = createFallbackModel;

// Test function to verify SMPL API
window.testSMPLAPI = async function() {
  console.log('🧪 Testing SMPL API...');
  
  try {
    // Test health endpoint
    const health = await window.getSMPLHealth();
    console.log('🏥 Health check result:', health);
    
    // Test model generation and load it into the scene
    console.log('🔄 Loading SMPL model into scene...');
    const model = await loadSMPLModel('test_user', 175, 75, 'male');
    
    if (model) {
      console.log('✅ SMPL model loaded successfully into scene');
      return { success: true, health, model };
    } else {
      throw new Error('Failed to load SMPL model into scene');
    }
  } catch (error) {
    console.error('❌ SMPL API test failed:', error);
    return { success: false, error: error.message };
  }
};

async function loadOBJWithMarkers(url, scene) {
  try {
    console.log("🔄 Loading OBJ from", url);
    
    // 1) Create a group to hold mesh + markers
    const root = new THREE.Group();
    scene.add(root);

    const mesh = await new THREE.OBJLoader().loadAsync(url);
    root.add(mesh);

    // 2) Compute original bounding box in mesh-local space
    const origBox    = new THREE.Box3().setFromObject(root);
    const origSize   = new THREE.Vector3();
    const origCenter= new THREE.Vector3();
    origBox.getSize(origSize);
    origBox.getCenter(origCenter);

    // 3) Pre-scale radius for markers (in local units)
    const radiusLocal = Math.min(origSize.x, origSize.y, origSize.z) * 0.02;

    // 4) Center mesh & markers at origin
    root.position.sub(origCenter);

    // 5) Scale whole model so its height is 2 meters
    const desiredHeight = 2.0;
    const scaleFactor   = desiredHeight / origSize.y;
    root.scale.setScalar(scaleFactor);

    // 6) Draw wireframe around final (scaled) box
    const finalBox   = new THREE.Box3().setFromObject(root);
    const finalSize  = new THREE.Vector3();
    finalBox.getSize(finalSize);

    const boxGeo = new THREE.BoxGeometry(
      finalSize.x, finalSize.y, finalSize.z
    );
    const edges = new THREE.EdgesGeometry(boxGeo);
    const wire = new THREE.LineSegments(
      edges,
      new THREE.LineBasicMaterial({ color: 0xff0000 })
    );
    // position in world coords:
    wire.position.copy(finalBox.getCenter(new THREE.Vector3()));
    scene.add(wire);

    // 7) Define your organs (rel coords in [0,1] of origSize)
    const organs = [
      { name: 'Kidney-Left',  rel: [0.3, 0.5, 0.25], color: 0x00ff00 },
      { name: 'Kidney-Right', rel: [0.7, 0.5, 0.25], color: 0x00ff00 },
      { name: 'Stomach',      rel: [0.5, 0.65, 0.4 ], color: 0xffff00 },
      { name: 'Pancreas',     rel: [0.55,0.6, 0.35], color: 0xff00ff },
      { name: 'Femur',        rel: [0.5, 0.1,  0.5 ], color: 0x0000ff },
    ];

    // 8) Place each marker **in local mesh coords** (before scale + center)
    organs.forEach(o => {
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(radiusLocal, 16, 16),
        new THREE.MeshStandardMaterial({ color: o.color, emissive: o.color })
      );
      marker.name = o.name;

      // local-position inside original bounding box:
      marker.position.set(
        origBox.min.x + o.rel[0] * origSize.x,
        origBox.min.y + o.rel[1] * origSize.y,
        origBox.min.z + o.rel[2] * origSize.z
      );

      // add to root: it will inherit centering+scale
      root.add(marker);
      markers[o.name] = marker;
      console.log(`🔖  Placed ${o.name} at local`, marker.position);
    });

    console.log("✅ Model + markers ready");
    return root;
  } catch (error) {
    console.error("❌ Error loading OBJ model:", error);
    return null;
  }
}

// Highlight logic called by the dropdown
window.highlightOrgan = function(name) {
  console.log(`🎯 Highlighting organ: ${name}`);
  
  // reset previous
  if (prevHighlight) {
    prevHighlight.material.emissive.setHex(prevHighlight.userData.baseEmissive);
    prevHighlight.scale.setScalar(1);
  }

  const mesh = markers[name];
  if (!mesh) {
    console.warn(`⚠️ Organ ${name} not found in markers`);
    return;
  }

  mesh.userData.baseEmissive = mesh.material.emissive.getHex();
  mesh.material.emissive.setHex(0xffffff);   // bright glow
  mesh.scale.setScalar(1.4);                // enlarge

  prevHighlight = mesh;
  console.log(`✅ Highlighted ${name}`);
};

function init() {
  if (isInitialized) {
    console.log('🚫 Already initialized, skipping...');
    return;
  }
  
  console.log('🚀 Initializing 3D Digital Twin...');
  isInitialized = true;
  
  // scene + camera + renderer
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x666666); // Much lighter background
  currentScene = scene;

  const camera = new THREE.PerspectiveCamera(
    50,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
  );
  camera.position.set(0, 2, 8); // Move camera back and up to see the full model
  camera.lookAt(0, 1, 0); // Look at the center of the model

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);
  
  console.log('✅ WebGL renderer initialized successfully');

  // lights
  scene.add(new THREE.AmbientLight(0xffffff, 0.8)); // Much brighter ambient light
  const dir = new THREE.DirectionalLight(0xffffff, 1.5); // Brighter directional light
  dir.position.set(5, 10, 7.5);
  scene.add(dir);
  
  // Add a second directional light from the front
  const frontLight = new THREE.DirectionalLight(0xffffff, 1.0);
  frontLight.position.set(0, 5, 10);
  scene.add(frontLight);
  
  // Add a point light near the model
  const pointLight = new THREE.PointLight(0xffffff, 1.0, 20);
  pointLight.position.set(0, 2, 5);
  scene.add(pointLight);

  // Add immediate visual feedback - a simple cube to verify rendering
  const testCube = new THREE.Mesh(
    new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshPhongMaterial({ color: 0xff0000, shininess: 100 })
  );
  testCube.position.set(3, 0, 0); // Move test cube to the right
  scene.add(testCube);
  console.log('🔴 Added test cube to the right');
  
  // Force an immediate render to test
  renderer.render(scene, camera);
  console.log('🎬 Forced immediate render');

  // orbit controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping    = true;
  controls.dampingFactor    = 0.05;
  controls.minDistance      = 2;
  controls.maxDistance      = 20;
  controls.maxPolarAngle    = Math.PI / 2;

  // Load default SMPL model instead of OBJ
  console.log('🔄 Waiting for SMPL API test...');
  
  // Don't load SMPL model automatically - wait for button click
  // The test cube is already visible to confirm rendering works

  // render loop
  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
    
    // Debug: Log scene children count occasionally
    if (Math.random() < 0.01) { // Log 1% of the time
      console.log(`🎬 Rendering scene with ${scene.children.length} objects`);
      console.log(`📷 Camera position:`, camera.position);
      console.log(`🎯 Camera target:`, controls.target);
    }
  })();

  // handle resize
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
  
  console.log('✅ 3D Digital Twin initialized successfully');
}

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', () => {
  console.log('📄 DOM loaded, starting initialization...');
  init();
});