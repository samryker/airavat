import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// will hold { "Kidney-Left": Mesh, ... }
let markers = {};
let prevHighlight = null;

async function loadOBJWithMarkers(url, scene) {
  // 1) Create a group to hold mesh + markers
  const root = new THREE.Group();
  scene.add(root);

  console.log("🔄 Loading OBJ from", url);
  const mesh = await new OBJLoader().loadAsync(url);
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
}

// Highlight logic called by the dropdown
window.highlightOrgan = function(name) {
  // reset previous
  if (prevHighlight) {
    prevHighlight.material.emissive.setHex(prevHighlight.userData.baseEmissive);
    prevHighlight.scale.setScalar(1);
  }

  const mesh = markers[name];
  if (!mesh) return;

  mesh.userData.baseEmissive = mesh.material.emissive.getHex();
  mesh.material.emissive.setHex(0xffffff);   // bright glow
  mesh.scale.setScalar(1.4);                // enlarge

  prevHighlight = mesh;
};

function init() {
  // scene + camera + renderer
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111111);

  const camera = new THREE.PerspectiveCamera(
    50,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
  );
  camera.position.set(0, 1, 5);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  // lights
  scene.add(new THREE.AmbientLight(0xffffff, 0.5));
  const dir = new THREE.DirectionalLight(0xffffff, 1);
  dir.position.set(5, 10, 7.5);
  scene.add(dir);

  // orbit controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping    = true;
  controls.dampingFactor    = 0.05;
  controls.minDistance      = 2;
  controls.maxDistance      = 20;
  controls.maxPolarAngle    = Math.PI / 2;

  // finally load the model + markers
  loadOBJWithMarkers('/models/male.obj', scene);

  // render loop
  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();

  // handle resize
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
}

init();
