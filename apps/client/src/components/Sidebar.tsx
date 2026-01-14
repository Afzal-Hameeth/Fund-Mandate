import React, { useState } from 'react';
import {useLocation, NavLink } from 'react-router-dom';
import {FiLayers, FiChevronLeft, FiChevronRight, FiFileText, FiEye } from 'react-icons/fi';

const Sidebar: React.FC = () => {
 
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);


  const navItems = [
    { label: 'Agents', path: '/', icon: FiLayers },
    { label: 'Fund Mandate', path: '/fund-mandate', icon: FiFileText },
    { label: 'Screening Agent', path: '/screening-agent', icon: FiEye },
  ];

  return (
    <aside
      className={`bg-white border-r border-gray-200 transition-all duration-300 flex flex-col ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        {!collapsed && <h2 className="font-bold text-lg text-gray-900">Agent Platform</h2>}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 hover:bg-gray-100 rounded-md"
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? <FiChevronRight size={18} /> : <FiChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
                isActive
                  ? 'bg-indigo-100 text-indigo-700 font-medium'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
              title={collapsed ? item.label : ''}
            >
              <Icon size={20} />
              {!collapsed && <span className="text-sm">{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
};

export default Sidebar;