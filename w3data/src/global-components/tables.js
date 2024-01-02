import React from 'react';
import { useParams } from 'react-router-dom';
import '../styles/Loading.css';
import '../styles/home.css';
import useExperimentalEffect from '../api-services/useExperimental_service';

const Tables = () => {
  const { username } = useParams();
  const { data, fieldNames} = useExperimentalEffect(username); 

  const renderTable = () => {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return <p>No data available.</p>;
    }

    return (
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              {fieldNames.map((fieldName) => (
                <th key={fieldName}>{fieldName}</th>
             ) )}
             
            </tr>
          </thead>
          <tbody>
            {data.map((item, index) => (
              <tr key={index}>
                <td>{item.Time}</td>
                {fieldNames.map((fieldName) => (
                  <td key={fieldName}>{item.Value}</td>
                ))}
               
              </tr>
          )  )}
          </tbody>
        </table>
      </div>
    );
  };
return (
    <div style={{width:'100%',height:'auto-fit'}}>      
    {renderTable()}        
    </div>
  );
};

export default Tables;