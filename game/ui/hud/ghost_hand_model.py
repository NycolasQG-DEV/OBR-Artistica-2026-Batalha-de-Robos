"""3D Hand Mesh Model Generator & Real-Time Skin Deformer for GhostHand UI."""
import math
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPolygonF

class Hand3DMeshModel:
    """3D Organic Hand Mesh with Linear Blend Skinning driven by MediaPipe landmarks."""

    def __init__(self, palm_thickness=18.0, focal_length=750.0):
        self.vertices = []        # Base rest-pose 3D relative vertices (x, y, z)
        self.faces = []           # Triangle/Quad faces [v1_idx, v2_idx, v3_idx, ...]
        self.skin_weights = []    # List of (landmark_index, weight) for each vertex
        self.palm_thickness = palm_thickness
        self.focal_length = focal_length
        
        self._build_procedural_hand_mesh()

    def _build_procedural_hand_mesh(self):
        """Builds a 3D organic human hand mesh topology bound to 21 landmarks."""
        self.vertices = []
        self.faces = []
        self.skin_weights = []

        # Landmark reference indices for fingers
        finger_chains = [
            [1, 2, 3, 4],     # Thumb
            [5, 6, 7, 8],     # Index
            [9, 10, 11, 12],  # Middle
            [13, 14, 15, 16], # Ring
            [17, 18, 19, 20]  # Pinky
        ]

        # Finger radii tapering from base to tip
        finger_radii = [
            [0.024, 0.022, 0.020, 0.016],  # Thumb
            [0.022, 0.020, 0.018, 0.014],  # Index
            [0.023, 0.021, 0.019, 0.015],  # Middle
            [0.021, 0.019, 0.017, 0.013],  # Ring
            [0.019, 0.017, 0.015, 0.012]   # Pinky
        ]

        num_sides = 8  # 8 radial vertices for smooth 3D cross-sections

        # 1. Build 3D Volumetric Finger Meshes
        for f_idx, chain in enumerate(finger_chains):
            radii = finger_radii[f_idx]
            ring_vertex_indices = []

            for node_idx, lm_id in enumerate(chain):
                r = radii[node_idx]
                ring = []
                for s in range(num_sides):
                    angle = (2.0 * math.pi * s) / num_sides
                    dx = r * math.cos(angle)
                    dy = r * math.sin(angle)
                    dz = 0.0

                    v_idx = len(self.vertices)
                    self.vertices.append((dx, dy, dz))
                    # Bind vertex to landmark
                    self.skin_weights.append([(lm_id, 1.0)])
                    ring.append(v_idx)

                ring_vertex_indices.append(ring)

            # Build Quad Faces connecting finger rings
            for r_i in range(len(ring_vertex_indices) - 1):
                r_curr = ring_vertex_indices[r_i]
                r_next = ring_vertex_indices[r_i + 1]
                for s in range(num_sides):
                    s_next = (s + 1) % num_sides
                    # Quad face: (curr_s, curr_s_next, next_s_next, next_s)
                    self.faces.append([r_curr[s], r_curr[s_next], r_next[s_next], r_next[s]])

            # Add Tip Cap (Dome)
            tip_lm = chain[-1]
            tip_ring = ring_vertex_indices[-1]
            tip_center_idx = len(self.vertices)
            self.vertices.append((0.0, 0.0, 0.010))
            self.skin_weights.append([(tip_lm, 1.0)])

            for s in range(num_sides):
                s_next = (s + 1) % num_sides
                self.faces.append([tip_ring[s], tip_ring[s_next], tip_center_idx])

        # 2. Build 3D Volumetric Palm Surface Mesh
        palm_landmarks = [0, 1, 5, 9, 13, 17]
        palm_front_ring = []
        palm_back_ring = []

        thickness = self.palm_thickness * 0.001

        for lm_id in palm_landmarks:
            # Front face vertex
            idx_front = len(self.vertices)
            self.vertices.append((0.0, 0.0, thickness))
            self.skin_weights.append([(lm_id, 1.0)])
            palm_front_ring.append(idx_front)

            # Back face vertex
            idx_back = len(self.vertices)
            self.vertices.append((0.0, 0.0, -thickness))
            self.skin_weights.append([(lm_id, 1.0)])
            palm_back_ring.append(idx_back)

        # Front Palm Polygons
        self.faces.append([palm_front_ring[0], palm_front_ring[1], palm_front_ring[2]])
        self.faces.append([palm_front_ring[0], palm_front_ring[2], palm_front_ring[3]])
        self.faces.append([palm_front_ring[0], palm_front_ring[3], palm_front_ring[4]])
        self.faces.append([palm_front_ring[0], palm_front_ring[4], palm_front_ring[5]])

        # Back Palm Polygons
        self.faces.append([palm_back_ring[0], palm_back_ring[2], palm_back_ring[1]])
        self.faces.append([palm_back_ring[0], palm_back_ring[3], palm_back_ring[2]])
        self.faces.append([palm_back_ring[0], palm_back_ring[4], palm_back_ring[3]])
        self.faces.append([palm_back_ring[0], palm_back_ring[5], palm_back_ring[4]])

    def deform_and_project(self, landmarks_3d, width, height):
        """Skin deforms the 3D hand mesh vertices using real-time 3D landmarks."""
        if not landmarks_3d or len(landmarks_3d) < 21:
            return []

        focal = self.focal_length
        deformed_pts = []

        # 1. Deform Vertices via Landmark Binding
        for v_idx, rest_v in enumerate(self.vertices):
            weights = self.skin_weights[v_idx]
            def_x, def_y, def_z = 0.0, 0.0, 0.0

            for lm_id, w in weights:
                lm = landmarks_3d[lm_id]
                def_x += w * (lm[0] + rest_v[0])
                def_y += w * (lm[1] + rest_v[1])
                def_z += w * (lm[2] + rest_v[2])

            # 3D Screen Projection
            X = (def_x - 0.5) * width
            Y = (def_y - 0.5) * height
            Z = def_z * width + 500.0

            scale = focal / max(Z, 100.0)
            screen_x = width / 2.0 + X * scale
            screen_y = height / 2.0 + Y * scale

            deformed_pts.append({
                "pt2d": QPointF(screen_x, screen_y),
                "pt3d": (X, Y, Z),
                "scale": scale
            })

        # 2. Compute 3D Face Polygons, Normals, and Lighting
        render_faces = []
        lx, ly, lz = 0.3, -0.6, 0.74  # 3D Directional Light

        for face in self.faces:
            pts2d = [deformed_pts[idx]["pt2d"] for idx in face]
            pts3d = [deformed_pts[idx]["pt3d"] for idx in face]

            # Face Normal calculation
            v0 = pts3d[0]
            v1 = pts3d[1]
            v2 = pts3d[2]

            ax, ay, az = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
            bx, by, bz = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]

            nx = ay * bz - az * by
            ny = az * bx - ax * bz
            nz = ax * by - ay * bx
            length = math.sqrt(nx*nx + ny*ny + nz*nz)
            if length > 1e-5:
                nx, ny, nz = nx/length, ny/length, nz/length
            else:
                nx, ny, nz = 0.0, 0.0, 1.0

            # Lighting calculations
            dot = max(0.25, nx * lx + ny * ly + nz * lz)
            fresnel = math.pow(1.0 - abs(nz), 1.3)
            avg_z = sum(p[2] for p in pts3d) / len(pts3d)

            render_faces.append({
                "poly": QPolygonF(pts2d),
                "z_depth": avg_z,
                "light": dot,
                "fresnel": fresnel
            })

        # Sort Faces Back-to-Front (Painter's Algorithm)
        render_faces.sort(key=lambda f: f["z_depth"], reverse=True)
        return render_faces
