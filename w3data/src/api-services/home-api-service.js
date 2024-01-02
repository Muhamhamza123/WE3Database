
// homeService.js


import axios from 'axios';
export const fetchUserProject = async (username, setUserProjects, setProjectCount, setLoading) => {
    try {
      const projectResponse = await axios.get(`https://we3data.onrender.com/user-projects/${username}`);
      setUserProjects(projectResponse.data.projects);
      setProjectCount(projectResponse.data.project_count);
      setTimeout(() => setLoading(false), 3000);
    } catch (error) {
      console.error('Error:', error);
      setTimeout(() => setLoading(false), 3000);
    }
  };
  
  export const updateProject = async (editedProject, editedDescription, setIsSuccessMessageVisible) => {
    try {
      const response = await axios.put(`https://we3data.onrender.com/update-project`, {
        project_name: editedProject.project_name,
        project_description: editedDescription,
      });
      if (response.data.success) {
        setIsSuccessMessageVisible(true);
      } else {
        console.error('Error updating project:', response.data.message);
      }
    } catch (error) {
      console.error('Error making the request:', error);
    }
  };
  
  