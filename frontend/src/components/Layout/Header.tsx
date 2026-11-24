import React from 'react';

const Header: React.FC = () => {
  return (
    <header className="header">
      <div className="breadcrumbs">
        <span>Home / Dashboard</span>
      </div>
      <div className="user-area">
        <div className="avatar">U</div>
      </div>
    </header>
  );
};

export default Header;
