import numpy as np
from stl import mesh
from scipy.spatial import ConvexHull, Delaunay

def load_mesh_points(stl_file_path):
    # Load the STL file
    mesh_data = mesh.Mesh.from_file(stl_file_path)
    all_points = np.concatenate([mesh_data.v0, mesh_data.v1, mesh_data.v2])
    
    # Calculate the bounding box and centroid
    min_coords = all_points.min(axis=0)
    max_coords = all_points.max(axis=0)
    centroid = np.mean(all_points, axis=0)
    
    return all_points, min_coords, max_coords, centroid

def get_internal_point(stl_file_path, offset_factor=0.2):
    # Load the STL file and compute the centroid
    all_points, min_coords, max_coords, centroid = load_mesh_points(stl_file_path)
    
    # Get the Delaunay triangulation to define inside/outside of the geometry
    delaunay = Delaunay(all_points)

    # Find the farthest point on the hull from the centroid
    distances = np.linalg.norm(all_points - centroid, axis=1)
    farthest_point = all_points[np.argmax(distances)]
    
    # Move inward from the farthest point along the vector towards the centroid
    direction_vector = centroid - farthest_point
    internal_point = farthest_point + direction_vector * offset_factor  # Offset towards inside

    # Check if the generated point is inside the geometry
    if delaunay.find_simplex(internal_point) >= 0:
        return internal_point
    else:
        print("Failed to place the internal point within offset distance.")
        return None

# Path to your STL file
stl_file_path = '/home/y95228da/Desktop/Cardio-app-Dania/Cardio-app-Dania/CAD/VOL04/wall_aorta.stl'
internal_point = get_internal_point(stl_file_path)

if internal_point is not None:
    print("Internal Point:", internal_point)
else:
    print("No internal point found.")

