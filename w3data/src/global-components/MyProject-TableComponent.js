// TableComponent.js
import React from 'react';

const TableComponent = ({ data, fieldNames, showTable, toggleView })=> {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return <p>No data available.</p>;
    }

    return (
      <div style={{width:'100%',overflow:'auto',height:'500px',marginBottom:'20px'}}>
         <button className='toggel_button' onClick={toggleView}>
        {showTable ? 'Show Graphs' : 'Show Table'}
      </button>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              {fieldNames.map((fieldName) => (
                <th key={fieldName}>{fieldName}</th>
              ))}
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
            ))}
          </tbody>
        </table>
      </div>
    );
  };

export default TableComponent;
